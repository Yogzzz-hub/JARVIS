/**
 * Baileys Transport Client Adapter for JARVIS EDGE.
 * Purely transport-layer I/O.
 * Does not contain AI, memory, system prompts, or shell commands.
 */

const path = require("path");
const fs = require("fs");
const pino = require("pino");
const { normalizeIncomingMessage, normalizePendingMessage, isPendingDecryption, isGroupJid } = require("./protocol");
const { saveMediaBuffer } = require("./media");
const { ConnectionState, ReconnectManager } = require("./reconnect");
const { ChatIndex, normJid, toSeconds } = require("./chat_index");
const { traceIncoming } = require("./incoming_trace");

// A message delivered on reconnect ("append": sent while the bridge was offline) older than this is history:
// JARVIS stores it but never answers, announces or runs it as a command.
const LIVE_WINDOW_S = 120;
// History sync when linking: unread messages of the last two weeks are stored, at most 5 per chat.
const HISTORY_MAX_AGE_S = 14 * 24 * 3600;
const HISTORY_PER_CHAT = 5;
const INBOX_HISTORY_TYPES = new Set([0, 3, 4, 6]); // bootstrap, recent, push names, on-demand in Baileys 6.7.24

// Optional dynamic import of Baileys in case environment is running in mock/test mode
let baileysModule = null;
try {
  baileysModule = require("@whiskeysockets/baileys");
} catch (e) {
  // Will log or gracefully handle if baileys is not installed yet
}

/**
 * Normalize a recipient to a WhatsApp JID. Names are resolved to numbers by the Python side;
 * anything that is neither a JID nor a phone number is rejected instead of silently failing.
 */
function normalizeJid(to) {
  if (!to || typeof to !== "string") {
    throw new Error("Missing recipient");
  }
  const trimmed = to.trim();
  if (trimmed.includes("@")) {
    return trimmed;
  }
  const digits = trimmed.replace(/\D/g, "");
  if (digits.length < 7 || digits.length > 15 || /[a-z]/i.test(trimmed)) {
    throw new Error(`Invalid WhatsApp recipient: ${trimmed}`);
  }
  return `${digits}@s.whatsapp.net`;
}

class BaileysClient {
  constructor({
    authDir,
    tempDir,
    onNormalizedMessage = null,
    onStatusChange = null,
    onRuntimeUpdate = null,
    onQrCode = null,
    onChatState = null
  }) {
    this.authDir = path.resolve(authDir || process.env.JARVIS_WHATSAPP_AUTH_DIR ||
      path.resolve(__dirname, "../../../data/whatsapp_auth_fresh_latency_test"));
    this.tempDir = path.resolve(tempDir || process.env.JARVIS_WHATSAPP_TEMP_DIR ||
      path.resolve(__dirname, "../../../data/whatsapp_temp"));
    // An unregistered session must not request pairing to a baked-in account.
    this.pairingNumber = process.env.WHATSAPP_PHONE_NUMBER || "";
    this.onNormalizedMessage = onNormalizedMessage;
    this.onStatusChange = onStatusChange;
    this.onRuntimeUpdate = onRuntimeUpdate;
    this.onQrCode = onQrCode;
    this.onChatState = onChatState;
    this.onPairingCode = null;
    this.lastPairingCode = null;

    this.sock = null;
    this.reconnect = new ReconnectManager({
      onStateChange: (state, meta) => {
        if (this.onStatusChange) {
          this.onStatusChange(state, meta);
        }
      }
    });

    this.logger = pino({ level: "trace", hooks: { logMethod: (args) => {
      const health = this.eventHealth;
      if (!health) return;
      const label = args.findLast(arg => typeof arg === "string") || "";
      const data = args.find(arg => arg && typeof arg === "object") || {};
      const categories = health.library_events ||= {};
      for (const category of ["sent ack", "sending receipt", "error in handling message", "processing offline",
          "retry", "decrypt", "sync", "flushing", "buffer"]) {
        if (label.toLowerCase().includes(category)) categories[category] = (categories[category] || 0) + 1;
      }
      if (label === "sent ack" && data.sent?.error) {
        const kind = String(data.recv?.attrs?.from || "").split("@")[1] || "unknown";
        const key = `${kind}:${data.sent.error}`;
        const nacks = health.nacks ||= {};
        nacks[key] = (nacks[key] || 0) + 1;
      }
      // Count errors without recording their text, nodes, credentials or message bodies.
      if (data.err || data.error) {
        const error = data.err || data.error;
        health.library_error_count = (health.library_error_count || 0) + 1;
        health.last_error_name = error.name || "Error";
        if (label === "failed to decrypt message") {
          const key = data.key || {};
          const raw = this._rawNodeMeta?.get(key.id) || {};
          const message = String(error.message || "");
          const reason = /bad mac/i.test(message) ? "BAD_MAC" :
            /pre.?key/i.test(message) || error.name === "PreKeyError" ? "PRE_KEY" :
            data.isSessionRecordError ? "SESSION_RECORD" : "OTHER_DECRYPT_ERROR";
          traceIncoming({ stage: "baileys_decrypt_error", event_type: "DECRYPT_ERROR",
            message_id: key.id || "", chat_jid: key.remoteJid || raw.chat_jid || "",
            from_me: Boolean(key.fromMe), participant: key.participant || data.author || "",
            message_type: data.messageType || raw.message_type || "",
            timestamp: raw.timestamp || null, generation: this.chatIndex?.generation || "",
            reason });
        }
      }
    } } });
    this.eventHealth = { counts: {}, event_map_counts: {}, listener_registered_at: null,
      socket_created_at: null, connection_open_at: null, received_pending_notifications: null,
      received_pending_notifications_at: null, is_online: null, last_connection_event: null,
      last_message_event: null, last_chat_event: null, last_receipt_event: null,
      buffer_started_at: null, buffer_released_at: null, buffer_active: false,
      buffered_event_count: 0, buffered_messages_upsert: 0, history_set_count: 0,
      last_message_jid_type: null, last_message_ignored_by_filter: null,
      presence_mode: "unavailable" };

    // WhatsApp's own unread badges per chat (what the phone shows), kept current from WhatsApp's events.
    this.chatIndex = new ChatIndex(path.resolve(this.authDir, "chat_index.json"), {
      onChange: (state) => {
        if (this.onChatState) this.onChatState(state);
      }
    });

    this.messageCache = new Map();
    this.cacheFile = path.resolve(this.authDir, "message_cache.json");
    try {
      if (fs.existsSync(this.cacheFile)) {
        const raw = JSON.parse(fs.readFileSync(this.cacheFile, "utf-8"));
        for (const [k, v] of Object.entries(raw)) {
          this.messageCache.set(k, v);
        }
      }
    } catch (e) {}
  }

  rememberNormalized(normalized) {
    if (!this.normalizedCache) this.normalizedCache = new Map();
    this.normalizedCache.set(normalized.message_id, normalized);
    if (this.normalizedCache.size > 500) {
      this.normalizedCache.delete(this.normalizedCache.keys().next().value);
    }
  }

  /** Group subject (name) for a group JID, cached; "" when unknown. Lets the owner name a group explicitly. */
  async groupName(jid) {
    if (!isGroupJid(jid) || !String(jid).endsWith("@g.us")) return "";
    if (!this.groupNames) this.groupNames = new Map();
    const hit = this.groupNames.get(jid);
    if (hit && Date.now() - hit.at < 6 * 3600 * 1000) return hit.name;
    let name = hit ? hit.name : "";
    try {
      if (this.sock && typeof this.sock.groupMetadata === "function") {
        const meta = await this.sock.groupMetadata(jid);
        name = (meta && meta.subject) || name;
      }
    } catch (e) {}
    this.groupNames.set(jid, { name, at: Date.now() });
    return name;
  }

  getNormalizedMessage(id) {
    return (this.normalizedCache && this.normalizedCache.get(id)) || null;
  }

  traceMessage(stage, raw, fields = {}) {
    const key = raw?.key || {};
    traceIncoming({ stage, event_type: "messages.upsert", message_id: key.id || "",
      chat_jid: key.remoteJid || "", from_me: Boolean(key.fromMe),
      participant: key.participant || "", message_type: Object.keys(raw?.message || {})[0] ||
        (isPendingDecryption(raw) ? "PENDING_DECRYPTION" : "EMPTY"),
      timestamp: toSeconds(raw?.messageTimestamp) || null,
      generation: this.chatIndex.generation, ...fields });
  }

  detachUpsertListener(sock) {
    const binding = this._upsertBinding;
    if (!binding || binding.sock !== sock) return;
    if (typeof sock.ev.off === "function") sock.ev.off("messages.upsert", binding.handler);
    else if (typeof sock.ev.removeListener === "function") sock.ev.removeListener("messages.upsert", binding.handler);
    this._upsertBinding = null;
  }

  notePendingNotifications(ready) {
    this.eventHealth.received_pending_notifications = ready;
    this.eventHealth.received_pending_notifications_at = new Date().toISOString();
    if (ready === true && this.onRuntimeUpdate) {
      this.onRuntimeUpdate(this.getStatus(), this.getChats());
    }
  }

  async getMessageWithMedia(id, chatId, download = false) {
    const found = this.getNormalizedMessage(id);
    if (!found || found.chat_id !== chatId) return null;
    if (!download || found.media_ref?.file_path) return found;
    if (!found.media_ref || !this.downloadMediaMessage || !this.sock) return null;
    const body = this.messageCache.get(id);
    if (!body) return null;
    if (found.media_ref.size_bytes > 25 * 1024 * 1024) throw new Error("Attachment exceeds 25 MB limit");
    const stream = await this.downloadMediaMessage({ key: { id, remoteJid: chatId, fromMe: found.is_from_me }, message: body }, "stream", {}, { logger: this.logger });
    const chunks = [];
    let size = 0;
    try {
      for await (const chunk of stream) {
        size += chunk.length;
        if (size > 25 * 1024 * 1024) throw new Error("Attachment exceeds 25 MB limit");
        chunks.push(chunk);
      }
    } finally { stream.destroy(); }
    const media = await saveMediaBuffer(Buffer.concat(chunks), found.media_ref.mimetype, found.media_ref.filename, this.tempDir);
    const updated = { ...found, media_ref: { ...found.media_ref, ...media, downloaded: true } };
    this.rememberNormalized(updated);
    return updated;
  }

  saveMessage(id, msg) {
    if (!id || !msg) return;
    this.messageCache.set(id, msg);
    if (this.messageCache.size > 500) {
      const firstKey = this.messageCache.keys().next().value;
      this.messageCache.delete(firstKey);
    }
    this.cacheDirty = true;
    if (!this.cacheWriteScheduled) {
      this.cacheWriteScheduled = true;
      setImmediate(() => this.flushMessageCache());
    }
  }

  async flushMessageCache() {
    if (this.cacheWriting) return this.cacheWritePromise;
    this.cacheWriting = true;
    this.cacheWritePromise = (async () => {
      try {
        while (this.cacheDirty) {
          this.cacheDirty = false;
          const data = JSON.stringify(Object.fromEntries(this.messageCache));
          await fs.promises.writeFile(this.cacheFile + ".tmp", data, "utf-8");
          await fs.promises.rename(this.cacheFile + ".tmp", this.cacheFile);
        }
      } catch (error) {
        this.eventHealth.cache_write_errors = (this.eventHealth.cache_write_errors || 0) + 1;
      } finally {
        this.cacheWriting = false;
        this.cacheWriteScheduled = false;
      }
    })();
    return this.cacheWritePromise;
  }

  async start() {
    if (this.sock) {
      return true;
    }
    if (!baileysModule) {
      this.reconnect.setState(ConnectionState.DEGRADED, "@whiskeysockets/baileys package not installed");
      return false;
    }

    const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, downloadMediaMessage } = baileysModule;

    if (!fs.existsSync(this.authDir)) {
      fs.mkdirSync(this.authDir, { recursive: true });
    }

    this.reconnect.setState(ConnectionState.CONNECTING, "Loading auth state");

    const { state, saveCreds } = await useMultiFileAuthState(this.authDir);
    this.eventHealth.live_direct_messages = 0;
    this.eventHealth.last_live_message_at = null;
    this.eventHealth.last_live_message_hash = null;
    this.eventHealth.received_pending_notifications = null;
    this.eventHealth.connection_open_at = null;
    this.authRegistered = Boolean(state.creds?.registered);
    // The chat list with unread counts arrives only as a history sync right after linking. An already linked
    // device is asked a few times, then no longer (waiting for a sync that never comes delays the first messages).
    this.wantHistory = !this.chatIndex.synced && this.chatIndex.historyAttempts < 3;

    try {
      this.sock = makeWASocket({
        auth: state,
        logger: this.logger,
        printQRInTerminal: false,
        markOnlineOnConnect: false,
        enableAutoSessionRecreation: process.env.JARVIS_WHATSAPP_SESSION_RECOVERY === "1",
        enableRecentMessageCache: process.env.JARVIS_WHATSAPP_SESSION_RECOVERY === "1",
        syncFullHistory: false,
        shouldSyncHistoryMessage: (msg) => {
          const accepted = Boolean(this.wantHistory && msg && INBOX_HISTORY_TYPES.has(msg.syncType));
          this.chatIndex.lastHistoryFilter = { sync_type: msg?.syncType ?? null, accepted,
            generation: this.chatIndex.generation, at: new Date().toISOString() };
          return accepted;
        },
        getMessage: async (key) => {
          if (process.env.JARVIS_WHATSAPP_READ_ONLY === "1") return undefined;
          if (key && key.id && this.messageCache.has(key.id)) {
            console.log(`[Baileys] Fulfilling retry request for message ${key.id}`);
            return this.messageCache.get(key.id);
          }
          return undefined;
        }
      });
      if (process.env.JARVIS_WHATSAPP_READ_ONLY === "1" && this.sock.messageRetryManager) {
        // Retry requests may repair decryption, but must not resend cached chat content.
        this.sock.messageRetryManager.getRecentMessage = () => undefined;
      }
      this.eventHealth.socket_created_at = new Date().toISOString();
    } catch (err) {
      this.reconnect.setState(ConnectionState.DEGRADED, `Socket init failed: ${err.message}`);
      return false;
    }

    const sock = this.sock;
    this.installEventTap(sock);
    this.bindEvents(this.sock, downloadMediaMessage);
    this.sock.ev.on("creds.update", saveCreds);

    if (!state.creds?.registered && this.pairingNumber) {
      setTimeout(async () => {
        try {
          let cleanNum = this.pairingNumber.replace(/[^0-9]/g, "");
          if (cleanNum.length === 10) cleanNum = "91" + cleanNum;
          if (this.sock && !this.sock.authState?.creds?.registered) {
            const code = await this.sock.requestPairingCode(cleanNum);
            this.lastPairingCode = code;
            console.log("\n============================================================");
            console.log(`   WHATSAPP PAIRING CODE FOR +${cleanNum}: ${code}`);
            console.log("   (In WhatsApp -> Linked Devices -> Link with Phone Number)");
            console.log("============================================================\n");
            if (this.onPairingCode) {
              this.onPairingCode(code);
            }
          }
        } catch (e) {
          // Fallback to QR code if pairing code request fails
        }
      }, 2500);
    }

    this.sock.ev.on("connection.update", (update) => {
      if (this.sock !== sock) return;
      const { connection, lastDisconnect, qr } = update;
      this.eventHealth.last_connection_event = new Date().toISOString();
      if (Object.hasOwn(update, "receivedPendingNotifications")) {
        this.notePendingNotifications(update.receivedPendingNotifications);
      }
      if (Object.hasOwn(update, "isOnline")) this.eventHealth.is_online = update.isOnline;

      if (qr) {
        this.reconnect.setState(ConnectionState.PAIRING_REQUIRED, "QR pairing needed");
        try {
          const qrcode = require("qrcode-terminal");
          console.log("\n============================================================");
          console.log("   SCAN THIS QR CODE IN WHATSAPP (Linked Devices)");
          console.log("============================================================\n");
          qrcode.generate(qr, { small: true });
          console.log("============================================================\n");
        } catch (e) {}
        if (this.onQrCode) {
          this.onQrCode(qr);
        }
      }

      if (connection === "close") {
        this.detachUpsertListener(sock);
        this.chatIndex.markPartial();
        this.sock = null;
        const statusCode = lastDisconnect?.error?.output?.statusCode;
        this.lastDisconnectCode = statusCode ?? null;
        console.log(`[Baileys] Connection closed (code: ${statusCode}). Checking reconnect...`);
        const isLoggedOut = statusCode === DisconnectReason?.loggedOut || statusCode === 401;

        if (isLoggedOut) {
          console.log("[Baileys] Session requires authentication (code 401). Auth files preserved for inspection.");
          this.reconnect.setState(ConnectionState.PAIRING_REQUIRED, "Session requires authentication");
          return;
        }

        const shouldReconnect = true;
        const delay = this.reconnect.onDisconnect(shouldReconnect, `Connection closed (code: ${statusCode})`);

        if (delay !== false) {
          console.log(`[Baileys] Reconnecting in ${delay}ms...`);
          setTimeout(() => this.start(), delay);
        }
      } else if (connection === "open") {
        this.connectedAt = new Date().toISOString();
        this.eventHealth.connection_open_at = this.connectedAt;
        this.sock.sendPresenceUpdate("unavailable").catch((err) => {
          this.eventHealth.presence_error = String(err?.message || err);
        });
        console.log("\n============================================================");
        console.log("   WHATSAPP CONNECTED & LOGGED IN SUCCESSFULLY!");
        console.log("============================================================\n");
        this.reconnect.onConnected();
        if (this.wantHistory) {
          this.chatIndex.historyAttempts += 1;
          this.chatIndex.touch(null);
        }
      }
    });

    return true;
  }

  installEventTap(sock) {
    const health = this.eventHealth;
    const ev = sock.ev;
    sock.ws.on("CB:message", node => {
      const nodeMeta = { chat_jid: node?.attrs?.from || "",
        message_type: node?.attrs?.type || "RAW_MESSAGE_NODE",
        timestamp: toSeconds(node?.attrs?.t) || null };
      if (node?.attrs?.id) {
        this._rawNodeMeta ||= new Map();
        this._rawNodeMeta.set(node.attrs.id, nodeMeta);
        if (this._rawNodeMeta.size > 2048) this._rawNodeMeta.delete(this._rawNodeMeta.keys().next().value);
      }
      traceIncoming({ stage: "baileys_raw_node", event_type: "CB:message",
        message_id: node?.attrs?.id || "", chat_jid: node?.attrs?.from || "",
        participant: node?.attrs?.participant || "", message_type: nodeMeta.message_type,
        timestamp: toSeconds(node?.attrs?.t) || null, generation: this.chatIndex.generation });
      const stats = health.raw_node_counts ||= {};
      const kind = String(node.attrs.from || "").split("@")[1] || "unknown";
      stats[kind] = (stats[kind] || 0) + 1;
      health.last_raw_node_at = new Date().toISOString();
      health.last_raw_node_hash = require("crypto").createHash("sha256")
        .update(String(node.attrs.id || "")).digest("hex").slice(0, 16);
      const offline = String(node.attrs.offline ?? "absent");
      const offlineKey = ["0", "1", "absent"].includes(offline) ? offline : "other";
      const values = health.offline_values ||= {};
      values[offlineKey] = (values[offlineKey] || 0) + 1;
    });
    sock.ws.on("CB:ib,,offline_preview", node => {
      health.offline_preview_count = (health.offline_preview_count || 0) + 1;
      health.last_offline_preview_at = new Date().toISOString();
      const preview = Array.isArray(node.content) && node.content.find(child => child.tag === "offline_preview");
      const count = Number(preview?.attrs?.count);
      health.offline_preview_items = Number.isFinite(count) ? count : null;
    });
    sock.ws.on("CB:ib,,offline", () => {
      health.offline_completion_count = (health.offline_completion_count || 0) + 1;
      health.last_offline_completion_at = new Date().toISOString();
    });
    const originalEmit = ev.emit.bind(ev);
    ev.emit = (name, payload) => {
      health.counts[name] = (health.counts[name] || 0) + 1;
      if (name === "messaging-history.set") health.history_set_count += 1;
      if (name === "messages.upsert") {
        for (const message of payload?.messages || [])
          this.traceMessage("baileys_emit", message, { upsert_type: payload?.type || "",
            message_count: (payload?.messages || []).length });
        const jid = payload?.messages?.[0]?.key?.remoteJid || "";
        health.last_message_jid_type = jid.endsWith("@lid") ? "LID" :
          jid.endsWith("@s.whatsapp.net") ? "PN" : isGroupJid(jid) ? "group_or_broadcast" : "other";
        health.last_message_ignored_by_filter = false;
        for (const message of payload?.messages || []) {
          health.latest_raw_timestamp = Math.max(health.latest_raw_timestamp || 0, toSeconds(message.messageTimestamp));
          if (isPendingDecryption(message)) health.pending_decryption_count = (health.pending_decryption_count || 0) + 1;
        }
      }
      if (health.buffer_active && name === "messages.upsert")
        health.buffered_messages_upsert += (payload?.messages || []).length;
      if (health.buffer_active && name !== "connection.update") health.buffered_event_count += 1;
      return originalEmit(name, payload);
    };
    const originalBuffer = ev.buffer.bind(ev);
    ev.buffer = (...args) => {
      health.buffer_active = true;
      health.buffer_started_at = new Date().toISOString();
      return originalBuffer(...args);
    };
    const originalFlush = ev.flush.bind(ev);
    ev.flush = (...args) => {
      const result = originalFlush(...args);
      if (result) {
        health.buffer_active = false;
        health.buffer_released_at = new Date().toISOString();
      }
      return result;
    };
    if (typeof ev.process === "function") ev.process((map) => {
      for (const name of Object.keys(map))
        health.event_map_counts[name] = (health.event_map_counts[name] || 0) + 1;
    });
    health.listener_registered_at = new Date().toISOString();
    // Explicit diagnostic only: one bounded backlog request, never a buffer flush or chat send.
    const batchProbe = Number(process.env.JARVIS_WHATSAPP_OFFLINE_BATCH_PROBE || 0);
    if (Number.isInteger(batchProbe) && batchProbe > 100 && batchProbe <= 1000) {
      const timer = setTimeout(() => {
        if (this.sock !== sock || !sock.ws.isOpen || health.received_pending_notifications === true) return;
        this.probeOfflineBatch(batchProbe).catch(() => {});
      }, 20000);
      timer.unref();
    }
  }

  async probeOfflineBatch(count) {
    if (!Number.isInteger(count) || count <= 100 || count > 1000) throw new Error("Invalid diagnostic batch size");
    if (this.offlineBatchProbeUsed) throw new Error("Offline batch diagnostic already used");
    if (!this.sock?.ws?.isOpen || typeof this.sock.sendNode !== "function") throw new Error("Socket not open");
    this.offlineBatchProbeUsed = true;
    this.eventHealth.offline_batch_probe = { count, requested_at: new Date().toISOString(), status: "STARTED" };
    try {
      await this.sock.sendNode({ tag: "ib", attrs: {}, content: [{ tag: "offline_batch", attrs: { count: String(count) } }] });
      this.eventHealth.offline_batch_probe.status = "SUBMITTED";
    } catch (error) {
      this.eventHealth.offline_batch_probe.status = "FAILED";
      throw error;
    }
  }

  /** Message, chat and receipt events of a socket (separate from start() so it can be tested without WhatsApp). */
  bindEvents(sock, downloadMediaMessage = null) {
    this.downloadMediaMessage = downloadMediaMessage;
    if (this._upsertBinding) this.detachUpsertListener(this._upsertBinding.sock);
    const onUpsert = async ({ messages, type }) => {
      for (const rawMsg of messages || []) this.traceMessage("upsert_handler", rawMsg, {
        upsert_type: type || "", message_count: (messages || []).length,
        reason: this.sock !== sock ? "STALE_SOCKET" : "" });
      if (this.sock !== sock) return;
      this.eventHealth.last_message_event = new Date().toISOString();
      if (type !== "notify" && type !== "append") {
        for (const rawMsg of messages || []) this.traceMessage("upsert_filter", rawMsg, { reason: "UNSUPPORTED_UPSERT_TYPE" });
        return;
      }
      this.chatIndex.chatEvents.messages_upsert += (messages || []).length;
      this.chatIndex.lastMessageEvent = new Date().toISOString();
      const nowS = Date.now() / 1000;

      for (const rawMsg of messages) {
        if (this.sock !== sock) {
          this.traceMessage("upsert_filter", rawMsg, { reason: "STALE_SOCKET_DURING_HANDLER" });
          return;
        }
        const fromMe = Boolean(rawMsg.key?.fromMe);
        const remote = rawMsg.key?.remoteJid || "";
        // "notify" = new; "append" = delivered on reconnect. Recent ones are new messages, older ones history.
        const live = type === "notify" || nowS - (toSeconds(rawMsg.messageTimestamp) || nowS) <= LIVE_WINDOW_S;
        // The owner's own messages are forwarded only from direct chats (flagged is_from_me) so JARVIS can
        // learn how the owner writes to each person; they are never treated as commands. In a group they only
        // mark the group as read.
        if (fromMe && isGroupJid(remote)) {
          this.traceMessage("upsert_filter", rawMsg, { reason: "OWN_GROUP_MESSAGE" });
          const own = normalizeIncomingMessage(rawMsg, null);
          if (own) this.chatIndex.noteMessage(own);
          continue;
        }

        // Not decrypted yet ("Waiting for this message"): forward a placeholder, never a body.
        if (isPendingDecryption(rawMsg)) {
          const pending = normalizePendingMessage(rawMsg);
          this.traceMessage("normalization", rawMsg, { normalization_result: pending ? "PENDING_DECRYPTION" : "REJECTED",
            reason: pending ? "BODY_NOT_DECRYPTED" : "PENDING_MISSING_ID_OR_CHAT" });
          if (pending && live && !fromMe && this.onNormalizedMessage) {
            this.onNormalizedMessage(pending);
          }
          continue;
        }

        let mediaRef = null;
        const msgType = Object.keys(rawMsg.message || {})[0];

        // Group media is never downloaded (JARVIS does not act on group chats unless asked): saves time and disk.
        // Neither is the media of old messages delivered on reconnect.
        if (
          live &&
          process.env.JARVIS_WHATSAPP_AUTO_DOWNLOAD === "1" &&
          !isGroupJid(remote) &&
          downloadMediaMessage &&
          (msgType === "imageMessage" ||
            msgType === "documentMessage" ||
            msgType === "audioMessage")
        ) {
          try {
            const buffer = await downloadMediaMessage(
              rawMsg,
              "buffer",
              {},
              { logger: this.logger, reuploadRequest: this.sock.updateMediaMessage }
            );
            const mime =
              rawMsg.message[msgType]?.mimetype ||
              (msgType === "imageMessage"
                ? "image/jpeg"
                : msgType === "audioMessage"
                ? "audio/ogg"
                : "application/octet-stream");
            const filenameHint = rawMsg.message[msgType]?.fileName || msgType;
            mediaRef = await saveMediaBuffer(buffer, mime, filenameHint, this.tempDir);
          } catch (mediaErr) {
            // Media download error handled gracefully
          }
        }

        if (live && rawMsg.key && rawMsg.key.id && rawMsg.message) {
          this.saveMessage(rawMsg.key.id, rawMsg.message);
        }

        const normalized = normalizeIncomingMessage(rawMsg, mediaRef, (decision) =>
          this.traceMessage("normalization", rawMsg, { normalization_result: decision.result,
            reason: decision.reason, message_type: decision.messageType || msgType || "" }));
        if (normalized) {
          if (!normalized.is_group && !fromMe && live &&
              toSeconds(rawMsg.messageTimestamp) * 1000 >= Date.parse(this.connectedAt || "")) {
            this.eventHealth.live_direct_messages = (this.eventHealth.live_direct_messages || 0) + 1;
            this.eventHealth.last_live_message_at = new Date().toISOString();
            this.eventHealth.last_live_message_hash = require("crypto").createHash("sha256")
              .update(String(normalized.message_id)).digest("hex").slice(0, 16);
          }
          if (normalized.is_group) {
            normalized.chat_name = (!live && this.chatIndex.nameOf(normJid(remote))) || (await this.groupName(remote));
          } else if (!rawMsg.pushName) normalized.sender_display_name = this.chatIndex.nameOf(normJid(remote)) || normalized.sender_display_name;
          if (!live) normalized.history = true;
          this.chatIndex.noteMessage(normalized);
          this.rememberNormalized(normalized);
        }
        if (normalized && this.onNormalizedMessage) {
          if (this.sock !== sock) {
            this.traceMessage("upsert_filter", rawMsg, { reason: "STALE_SOCKET_BEFORE_FORWARD" });
            return;
          }
          this.onNormalizedMessage(normalized);
        }
      }
    };
    sock.ev.on("messages.upsert", onUpsert);
    this._upsertBinding = { sock, handler: onUpsert };

    // Unread badges: WhatsApp's chat list at link time, then its live updates.
    sock.ev.on("messaging-history.set", ({ chats, contacts, messages, isLatest, syncType, progress, chunkOrder }) => {
      try {
        this.onHistory(chats || [], contacts || [], messages || [],
          { isLatest: isLatest === true, syncType, progress, chunkOrder });
      } catch (err) {
        console.error("[Baileys] History sync handling failed:", err.message);
      }
    });
    sock.ev.on("chats.upsert", (chats) => {
      this.eventHealth.last_chat_event = new Date().toISOString();
      this.chatIndex.chatEvents.upsert += (chats || []).length;
      this.chatIndex.applyChats(chats, { absolute: true });
    });
    sock.ev.on("chats.update", (updates) => {
      this.eventHealth.last_chat_event = new Date().toISOString();
      this.chatIndex.chatEvents.update += (updates || []).length;
      this.chatIndex.applyChats(updates);
    });
    const onContacts = (list) => {
      for (const ct of list || []) {
        if (!ct || !ct.id) continue;
        if (ct.name) this.chatIndex.setName(ct.id, ct.name);
        else if (ct.notify || ct.verifiedName) this.chatIndex.setName(ct.id, ct.notify || ct.verifiedName, { weak: true });
      }
    };
    sock.ev.on("contacts.upsert", onContacts);
    sock.ev.on("contacts.update", onContacts);
    // The owner read a group on the phone (their own read receipt).
    sock.ev.on("message-receipt.update", (updates) => {
      this.eventHealth.last_receipt_event = new Date().toISOString();
      for (const { key, receipt } of updates || []) {
        if (key && receipt && receipt.readTimestamp && this.isMe(receipt.userJid)) {
          this.chatIndex.markRead(key.remoteJid);
        }
      }
    });

    // A message that was a placeholder can be decrypted later: forward the real body once, same message_id
    // (Python de-duplicates by message_id, so this can never create a second reply).
    sock.ev.on("messages.update", (updates) => {
      if (this.sock !== sock) return;
      for (const { key, update } of updates || []) {
        this.traceMessage("baileys_update", { key, message: update?.message,
          messageTimestamp: update?.messageTimestamp }, { event_type: "messages.update",
          reason: !update?.message ? "NO_MESSAGE_BODY" : key?.fromMe ? "OWN_MESSAGE" : "" });
        // READ / PLAYED on someone else's message: the owner opened that chat on the phone.
        if (key && update && !key.fromMe && typeof update.status === "number" && update.status >= 4) {
          this.chatIndex.markRead(key.remoteJid);
        }
        if (!key || !update || !update.message || key.fromMe) continue;
        const rawMsg = { key, message: update.message, pushName: update.pushName, messageTimestamp: update.messageTimestamp };
        this.saveMessage(key.id, update.message);
        const normalized = normalizeIncomingMessage(rawMsg, null, (decision) =>
          this.traceMessage("normalization", rawMsg, { event_type: "messages.update",
            normalization_result: decision.result, reason: decision.reason,
            message_type: decision.messageType || "" }));
        if (normalized && this.onNormalizedMessage) {
          if (normalized.is_group) {
            const cached = this.groupNames && this.groupNames.get(key.remoteJid);
            normalized.chat_name = cached ? cached.name : "";
          }
          this.rememberNormalized(normalized);
          this.onNormalizedMessage(normalized);
        }
      }
    });
  }

  isMe(jid) {
    const me = this.sock && this.sock.user;
    if (!jid || !me) return false;
    const id = normJid(jid);
    return id === normJid(me.id) || (me.lid ? id === normJid(me.lid) : false);
  }

  /**
   * History sync (right after linking): WhatsApp's chat list with exact unread counts, contact names and recent
   * messages. The unread messages themselves are forwarded flagged ``history`` - stored, never answered.
   */
  onHistory(chats, contacts, messages, meta = {}) {
    const times = messages.map((m) => toSeconds(m.messageTimestamp)).filter(Boolean);
    this.chatIndex.recordHistory({ sync_type: meta.syncType ?? null, is_latest: Boolean(meta.isLatest),
      progress: meta.progress ?? null, chunk_order: meta.chunkOrder ?? null,
      chat_count: chats.length, contact_count: contacts.length, message_count: messages.length,
      oldest_message_timestamp: times.length ? times.reduce((a, b) => Math.min(a, b), Infinity) : null,
      newest_message_timestamp: times.length ? times.reduce((a, b) => Math.max(a, b), 0) : null });
    for (const ct of contacts) {
      if (ct && ct.id && (ct.name || ct.notify)) this.chatIndex.setName(ct.id, ct.name || ct.notify, { weak: !ct.name });
    }
    this.chatIndex.applyChats(chats, { absolute: true });
    if (meta.isLatest) this.chatIndex.markSynced();

    const byChat = new Map();
    for (const m of messages) {
      const jid = normJid(m && m.key && m.key.remoteJid);
      if (!jid || !m.message) continue;
      if (!byChat.has(jid)) byChat.set(jid, []);
      byChat.get(jid).push(m);
    }
    const nowS = Date.now() / 1000;
    let forwarded = 0;
    for (const [jid, list] of byChat) {
      list.sort((a, b) => toSeconds(b.messageTimestamp) - toSeconds(a.messageTimestamp));
      const newest = normalizeIncomingMessage(list[0], null);
      if (newest) this.chatIndex.noteMessage(newest, { keepUnread: true });
      const chat = this.chatIndex.chats.get(jid);
      const unread = chat ? chat.unread : 0;
      if (!unread || !this.onNormalizedMessage) continue;
      const incoming = list.filter((m) => !m.key.fromMe && !isPendingDecryption(m)).slice(0, Math.min(unread, HISTORY_PER_CHAT));
      for (const m of incoming) {
        if (nowS - toSeconds(m.messageTimestamp) > HISTORY_MAX_AGE_S || forwarded >= 400) continue;
        const normalized = normalizeIncomingMessage(m, null);
        if (!normalized) continue;
        this.saveMessage(m.key.id, m.message);
        this.rememberNormalized(normalized);
        normalized.history = true;
        if (normalized.is_group) normalized.chat_name = this.chatIndex.nameOf(jid);
        else if (!m.pushName) normalized.sender_display_name = this.chatIndex.nameOf(jid) || normalized.sender_display_name;
        this.onNormalizedMessage(normalized);
        forwarded += 1;
      }
    }
  }

  getChats() {
    return this.chatIndex.snapshot();
  }

  async ensureRecipient(to) {
    const jid = normalizeJid(to);
    if (jid.endsWith("@s.whatsapp.net") && typeof this.sock.onWhatsApp === "function") {
      try {
        const [result] = await this.sock.onWhatsApp(jid);
        if (result && result.exists === false) {
          throw new Error(`${jid.split("@")[0]} is not registered on WhatsApp`);
        }
      } catch (err) {
        if (/not registered on WhatsApp/.test(err.message)) {
          throw err;
        }
        // Lookup failures (rate limits, transient errors) should not block sending.
      }
    }
    return jid;
  }

  async sendTextMessage(toJid, text, quoted = null) {
    if (!this.sock) {
      throw new Error("Baileys socket is not connected");
    }
    toJid = await this.ensureRecipient(toJid);

    const payload = { text };
    const options = quoted ? { quoted } : {};
    let sent;
    try { sent = await this.sock.sendMessage(toJid, payload, options); }
    catch (error) { error.outcomeUnknown = true; throw error; }
    if (sent && sent.key && sent.key.id && sent.message) {
      this.saveMessage(sent.key.id, sent.message);
    }
    return {
      message_id: sent?.key?.id || null,
      timestamp: sent?.messageTimestamp || null,
      status: sent?.key?.id ? "SENT" : "UNCERTAIN"
    };
  }

  async sendMediaMessage(toJid, filePath, mimeType, caption = "", isVoiceNote = false) {
    if (!this.sock) {
      throw new Error("Baileys socket is not connected");
    }
    toJid = await this.ensureRecipient(toJid);

    const stat = await fs.promises.stat(filePath);
    if (!stat.isFile() || stat.size > 25 * 1024 * 1024) throw new Error("Media must be a file at most 25 MB");
    const fileBuffer = await fs.promises.readFile(filePath);
    let messageContent = {};

    if (isVoiceNote || mimeType.includes("audio")) {
      messageContent = {
        audio: fileBuffer,
        mimetype: mimeType || "audio/ogg; codecs=opus",
        ptt: Boolean(isVoiceNote)
      };
    } else if (mimeType.includes("image")) {
      messageContent = {
        image: fileBuffer,
        caption: caption
      };
    } else {
      messageContent = {
        document: fileBuffer,
        mimetype: mimeType || "application/octet-stream",
        fileName: path.basename(filePath),
        caption: caption
      };
    }

    let sent;
    try { sent = await this.sock.sendMessage(toJid, messageContent); }
    catch (error) { error.outcomeUnknown = true; throw error; }
    if (sent && sent.key && sent.key.id && sent.message) {
      this.saveMessage(sent.key.id, sent.message);
    }
    return {
      message_id: sent?.key?.id || null,
      timestamp: sent?.messageTimestamp || null,
      status: sent?.key?.id ? "SENT" : "UNCERTAIN"
    };
  }

  async disconnect() {
    this.reconnect.reset();
    await this.flushMessageCache();
    if (this.sock) {
      this.detachUpsertListener(this.sock);
      try {
        this.sock.end();
      } catch (e) {
        // Ignore disconnect error
      }
      this.sock = null;
    }
  }

  getStatus() {
    const bridgeRoot = path.resolve(__dirname, "..");
    let commit = null;
    try {
      commit = require("child_process").execFileSync("git", ["rev-parse", "HEAD"],
        { cwd: bridgeRoot, encoding: "utf8", timeout: 1000 }).trim();
    } catch (e) {}
    let authFiles = 0;
    let authModified = null;
    try {
      const files = fs.readdirSync(this.authDir);
      authFiles = files.length;
      authModified = new Date(Math.max(...files.map((name) => fs.statSync(path.join(this.authDir, name)).mtimeMs))).toISOString();
    } catch (e) {}
    const { chats: _chats, ...diagnostics } = this.chatIndex.snapshot();
    return {
      state: this.reconnect.getState(),
      user: this.sock?.user || null,
      pairing_code: this.lastPairingCode,
      identity: {
        bridge_version: require("../package.json").version,
        git_commit: commit,
        source_modified_at: fs.statSync(__filename).mtime.toISOString(),
        process_pid: process.pid,
        process_started_at: new Date(Date.now() - process.uptime() * 1000).toISOString(),
        connected_at: this.connectedAt || null,
        working_directory: process.cwd(),
        script_path: path.resolve(__dirname, "index.js"),
        package_root: bridgeRoot,
        package_json_path: path.join(bridgeRoot, "package.json"),
        baileys_version: require(path.join(bridgeRoot, "node_modules/@whiskeysockets/baileys/package.json")).version,
        auth_path: this.authDir,
        auth_file_count: authFiles,
        auth_last_modified: authModified,
        auth_registered: Boolean(this.sock?.authState?.creds?.registered),
        auth_registered_on_load: Boolean(this.authRegistered),
        last_disconnect_code: this.lastDisconnectCode ?? null,
        chat_index_path: this.chatIndex.file,
        store_path: this.cacheFile,
        sync_generation: this.chatIndex.generation
      },
      event_health: { ...this.eventHealth, buffer_active: this.sock?.ev.isBuffering() ?? false },
      diagnostics
    };
  }
}

module.exports = {
  BaileysClient,
  normalizeJid
};
