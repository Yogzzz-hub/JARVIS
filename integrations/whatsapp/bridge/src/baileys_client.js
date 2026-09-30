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

// A message delivered on reconnect ("append": sent while the bridge was offline) older than this is history:
// JARVIS stores it but never answers, announces or runs it as a command.
const LIVE_WINDOW_S = 120;
// History sync when linking: unread messages of the last two weeks are stored, at most 5 per chat.
const HISTORY_MAX_AGE_S = 14 * 24 * 3600;
const HISTORY_PER_CHAT = 5;
const HISTORY_FULL = 2; // proto.HistorySync.HistorySyncType.FULL (years of messages: never requested)

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
    onQrCode = null,
    onChatState = null
  }) {
    this.authDir = authDir || path.resolve(__dirname, "../../../data/whatsapp_auth");
    this.tempDir = tempDir || path.resolve(__dirname, "../../../data/whatsapp_temp");
    this.pairingNumber = process.env.WHATSAPP_PHONE_NUMBER || "916381456199";
    this.onNormalizedMessage = onNormalizedMessage;
    this.onStatusChange = onStatusChange;
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

    this.logger = pino({ level: "silent" });

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

  saveMessage(id, msg) {
    if (!id || !msg) return;
    this.messageCache.set(id, msg);
    if (this.messageCache.size > 500) {
      const firstKey = this.messageCache.keys().next().value;
      this.messageCache.delete(firstKey);
    }
    try {
      const obj = Object.fromEntries(this.messageCache);
      fs.writeFileSync(this.cacheFile, JSON.stringify(obj, null, 2), "utf-8");
    } catch (e) {}
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
    // The chat list with unread counts arrives only as a history sync right after linking. An already linked
    // device is asked a few times, then no longer (waiting for a sync that never comes delays the first messages).
    this.wantHistory = !this.chatIndex.synced && this.chatIndex.historyAttempts < 3;

    try {
      this.sock = makeWASocket({
        auth: state,
        logger: this.logger,
        printQRInTerminal: false,
        syncFullHistory: false,
        shouldSyncHistoryMessage: (msg) => Boolean(this.wantHistory) && msg && msg.syncType !== HISTORY_FULL,
        getMessage: async (key) => {
          if (key && key.id && this.messageCache.has(key.id)) {
            console.log(`[Baileys] Fulfilling retry request for message ${key.id}`);
            return this.messageCache.get(key.id);
          }
          return undefined;
        }
      });
    } catch (err) {
      this.reconnect.setState(ConnectionState.DEGRADED, `Socket init failed: ${err.message}`);
      return false;
    }

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
      const { connection, lastDisconnect, qr } = update;

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
        this.sock = null;
        const statusCode = lastDisconnect?.error?.output?.statusCode;
        console.log(`[Baileys] Connection closed (code: ${statusCode}). Checking reconnect...`);
        const isLoggedOut = statusCode === DisconnectReason?.loggedOut || statusCode === 401;

        if (isLoggedOut) {
          console.log("[Baileys] Session logged out / expired (code 401). Clearing stale auth files to prompt new pairing...");
          this.chatIndex.reset();
          try {
            fs.rmSync(this.authDir, { recursive: true, force: true });
          } catch (e) {}
          setTimeout(() => this.start(), 1500);
          return;
        }

        const shouldReconnect = true;
        const delay = this.reconnect.onDisconnect(shouldReconnect, `Connection closed (code: ${statusCode})`);

        if (delay !== false) {
          console.log(`[Baileys] Reconnecting in ${delay}ms...`);
          setTimeout(() => this.start(), delay);
        }
      } else if (connection === "open") {
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

    this.bindEvents(this.sock, downloadMediaMessage);

    return true;
  }

  /** Message, chat and receipt events of a socket (separate from start() so it can be tested without WhatsApp). */
  bindEvents(sock, downloadMediaMessage = null) {
    sock.ev.on("messages.upsert", async ({ messages, type }) => {
      if (type !== "notify" && type !== "append") return;
      const nowS = Date.now() / 1000;

      for (const rawMsg of messages) {
        const fromMe = Boolean(rawMsg.key?.fromMe);
        const remote = rawMsg.key?.remoteJid || "";
        // "notify" = new; "append" = delivered on reconnect. Recent ones are new messages, older ones history.
        const live = type === "notify" || nowS - (toSeconds(rawMsg.messageTimestamp) || nowS) <= LIVE_WINDOW_S;
        // The owner's own messages are forwarded only from direct chats (flagged is_from_me) so JARVIS can
        // learn how the owner writes to each person; they are never treated as commands. In a group they only
        // mark the group as read.
        if (fromMe && isGroupJid(remote)) {
          const own = normalizeIncomingMessage(rawMsg, null);
          if (own) this.chatIndex.noteMessage(own);
          continue;
        }

        // Not decrypted yet ("Waiting for this message"): forward a placeholder, never a body.
        if (isPendingDecryption(rawMsg)) {
          const pending = normalizePendingMessage(rawMsg);
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

        const normalized = normalizeIncomingMessage(rawMsg, mediaRef);
        if (normalized) {
          if (normalized.is_group) {
            normalized.chat_name = (!live && this.chatIndex.nameOf(normJid(remote))) || (await this.groupName(remote));
          } else if (!rawMsg.pushName) normalized.sender_display_name = this.chatIndex.nameOf(normJid(remote)) || normalized.sender_display_name;
          if (!live) normalized.history = true;
          this.chatIndex.noteMessage(normalized);
          this.rememberNormalized(normalized);
        }
        if (normalized && this.onNormalizedMessage) {
          this.onNormalizedMessage(normalized);
        }
      }
    });

    // Unread badges: WhatsApp's chat list at link time, then its live updates.
    sock.ev.on("messaging-history.set", ({ chats, contacts, messages }) => {
      try {
        this.onHistory(chats || [], contacts || [], messages || []);
      } catch (err) {
        console.error("[Baileys] History sync handling failed:", err.message);
      }
    });
    sock.ev.on("chats.upsert", (chats) => this.chatIndex.applyChats(chats, { absolute: true }));
    sock.ev.on("chats.update", (updates) => this.chatIndex.applyChats(updates));
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
      for (const { key, receipt } of updates || []) {
        if (key && receipt && receipt.readTimestamp && this.isMe(receipt.userJid)) {
          this.chatIndex.markRead(key.remoteJid);
        }
      }
    });

    // A message that was a placeholder can be decrypted later: forward the real body once, same message_id
    // (Python de-duplicates by message_id, so this can never create a second reply).
    sock.ev.on("messages.update", (updates) => {
      for (const { key, update } of updates || []) {
        // READ / PLAYED on someone else's message: the owner opened that chat on the phone.
        if (key && update && !key.fromMe && typeof update.status === "number" && update.status >= 4) {
          this.chatIndex.markRead(key.remoteJid);
        }
        if (!key || !update || !update.message || key.fromMe) continue;
        const rawMsg = { key, message: update.message, pushName: update.pushName, messageTimestamp: update.messageTimestamp };
        const normalized = normalizeIncomingMessage(rawMsg, null);
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
  onHistory(chats, contacts, messages) {
    for (const ct of contacts) {
      if (ct && ct.id && (ct.name || ct.notify)) this.chatIndex.setName(ct.id, ct.name || ct.notify, { weak: !ct.name });
    }
    this.chatIndex.applyChats(chats, { absolute: true });
    if (chats.length) this.chatIndex.markSynced();

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
    const sent = await this.sock.sendMessage(toJid, payload, options);
    if (sent && sent.key && sent.key.id && sent.message) {
      this.saveMessage(sent.key.id, sent.message);
    }
    return {
      message_id: sent.key.id,
      timestamp: sent.messageTimestamp,
      status: "SENT"
    };
  }

  async sendMediaMessage(toJid, filePath, mimeType, caption = "", isVoiceNote = false) {
    if (!this.sock) {
      throw new Error("Baileys socket is not connected");
    }
    toJid = await this.ensureRecipient(toJid);

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

    const sent = await this.sock.sendMessage(toJid, messageContent);
    if (sent && sent.key && sent.key.id && sent.message) {
      this.saveMessage(sent.key.id, sent.message);
    }
    return {
      message_id: sent.key.id,
      timestamp: sent.messageTimestamp,
      status: "SENT"
    };
  }

  async disconnect() {
    this.reconnect.reset();
    if (this.sock) {
      try {
        this.sock.end();
      } catch (e) {
        // Ignore disconnect error
      }
      this.sock = null;
    }
  }

  getStatus() {
    return {
      state: this.reconnect.getState(),
      user: this.sock?.user || null,
      pairing_code: this.lastPairingCode
    };
  }
}

module.exports = {
  BaileysClient,
  normalizeJid
};
