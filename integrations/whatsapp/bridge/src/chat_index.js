/**
 * WhatsApp's own unread state per chat, as the phone shows it: unread badge count, name and last message.
 * Transport data only (counts, names, a short preview). Saved next to the auth files so the counts survive a
 * bridge restart - WhatsApp sends the full chat list only once, when the device is linked.
 */

const fs = require("fs");
const { randomUUID } = require("crypto");
const { isGroupJid } = require("./protocol");

const MAX_CHATS = 600;
const MAX_NAMES = 3000;

/** "9199...:12@s.whatsapp.net" -> "9199...@s.whatsapp.net" (device suffix removed). */
function normJid(jid) {
  const s = String(jid || "");
  const at = s.indexOf("@");
  if (at < 0) return s;
  return s.slice(0, at).split(":")[0] + s.slice(at);
}

/** Status updates, broadcast lists and channels are not chats with an unread badge. */
function skipJid(jid) {
  return !jid || jid.startsWith("status@") || jid.endsWith("@broadcast") || jid.endsWith("@newsletter");
}

/** Seconds from a number, a numeric string or a protobuf Long. */
function toSeconds(value) {
  if (value === null || value === undefined) return 0;
  if (typeof value === "object") {
    if (typeof value.toNumber === "function") return value.toNumber();
    if (typeof value.low === "number") return value.low >>> 0;
  }
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

class ChatIndex {
  constructor(file = null, { onChange = null, debounceMs = 1500 } = {}) {
    this.file = file;
    this.onChange = onChange;
    this.debounceMs = debounceMs;
    this.chats = new Map();
    this.names = new Map();
    this.synced = false; // WhatsApp sent the chat list (history sync when linking): the counts are complete
    this.generation = randomUUID();
    this.syncedGeneration = null;
    this.lastHistoryEvent = null;
    this.lastChatStateEvent = null;
    this.lastMessageEvent = null;
    this.historyEvents = [];
    this.lastHistoryFilter = null;
    this.chatEvents = { upsert: 0, update: 0, messages_upsert: 0 };
    this.historyAttempts = 0;
    this.dirty = new Set();
    this.timer = null;
    this.load();
  }

  load() {
    if (!this.file) return;
    try {
      if (!fs.existsSync(this.file)) return;
      const raw = JSON.parse(fs.readFileSync(this.file, "utf-8"));
      // A saved chat list is a cache, not proof that this connection has received
      // a complete history snapshot. Keep its counts for provisional results.
      this.synced = false;
      this.historyAttempts = 0;
      this.storeAgeSeconds = Math.max(0, (Date.now() - fs.statSync(this.file).mtimeMs) / 1000);
      for (const c of raw.chats || []) {
        if (c && c.jid) this.chats.set(c.jid, c);
      }
      for (const [k, v] of Object.entries(raw.names || {})) this.names.set(k, v);
    } catch (e) {}
  }

  save() {
    if (!this.file) return;
    try {
      const chats = [...this.chats.values()].sort((a, b) => b.lastTs - a.lastTs).slice(0, MAX_CHATS);
      const names = Object.fromEntries([...this.names.entries()].slice(-MAX_NAMES));
      fs.writeFileSync(
        this.file,
        JSON.stringify({ synced: this.synced, history_attempts: this.historyAttempts, chats, names }),
        "utf-8"
      );
    } catch (e) {}
  }

  chat(jid) {
    let c = this.chats.get(jid);
    if (!c) {
      c = { jid, name: "", pushName: "", unread: 0, lastTs: 0, isGroup: isGroupJid(jid),
            lastText: "", lastSender: "", lastFromMe: false };
      this.chats.set(jid, c);
    }
    return c;
  }

  /** Contact name for a person's JID. ``weak`` (the name they set themselves) never replaces a saved name. */
  setName(jid, name, { weak = false } = {}) {
    const id = normJid(jid);
    if (!id || !name || typeof name !== "string" || isGroupJid(id)) return;
    if (weak && this.names.has(id)) return;
    if (this.names.get(id) !== name) {
      this.names.set(id, name);
      if (this.chats.has(id)) this.touch(id);
    }
  }

  nameOf(jid) {
    const c = this.chats.get(jid);
    return (c && c.name) || this.names.get(jid) || (c && c.pushName) || "";
  }

  /**
   * Chat list updates. ``absolute`` (history sync): unreadCount is the badge itself. Live updates follow
   * Baileys: a positive count is new unread messages, 0 = read, -1 = marked unread, null = no change.
   */
  applyChats(list, { absolute = false } = {}) {
    this.lastChatStateEvent = new Date().toISOString();
    for (const u of list || []) {
      const jid = normJid(u && u.id);
      if (skipJid(jid)) continue;
      const c = this.chat(jid);
      if (u.name && typeof u.name === "string") c.name = u.name;
      else if (u.subject && typeof u.subject === "string") c.name = u.subject;
      const n = u.unreadCount;
      if (typeof n === "number") {
        if (absolute) c.unread = n < 0 ? 1 : n;
        else if (n > 0) c.unread += n;
        else if (n === 0) c.unread = 0;
        else c.unread = Math.max(c.unread, 1);
      }
      const ts = toSeconds(u.conversationTimestamp);
      if (ts) c.lastTs = Math.max(c.lastTs, ts);
      this.touch(jid);
    }
  }

  /**
   * A message seen in a chat (normalized by protocol.js): keeps the last-message preview current. The owner
   * writing the newest message in a chat reads it (WhatsApp clears the badge); ``keepUnread`` for history sync,
   * whose counts are already exact.
   */
  noteMessage(msg, { keepUnread = false } = {}) {
    this.lastMessageEvent = new Date().toISOString();
    const jid = normJid(msg && msg.chat_id);
    if (skipJid(jid)) return;
    const c = this.chat(jid);
    const ts = Math.floor(Date.parse(msg.timestamp) / 1000) || Math.floor(Date.now() / 1000);
    if (msg.is_from_me && !keepUnread && ts >= c.lastTs) c.unread = 0;
    if (ts >= c.lastTs || !c.lastText) {
      c.lastTs = Math.max(c.lastTs, ts);
      c.lastText = String(msg.text || (msg.type && msg.type !== "text" ? `[${msg.type.replace("_", " ")}]` : "")).slice(0, 300);
      c.lastSender = msg.is_from_me ? "" : msg.sender_display_name || "";
      c.lastFromMe = Boolean(msg.is_from_me);
    }
    if (msg.is_group && msg.chat_name) c.name = msg.chat_name;
    if (!msg.is_group && !msg.is_from_me && msg.sender_display_name) c.pushName = msg.sender_display_name;
    this.touch(jid);
  }

  markRead(jid) {
    const id = normJid(jid);
    const c = this.chats.get(id);
    if (!c || c.unread === 0) return;
    c.unread = 0;
    this.touch(id);
  }

  /** Logged out: the next link starts from WhatsApp's chat list again. */
  reset() {
    this.chats.clear();
    this.names.clear();
    this.synced = false;
    this.generation = randomUUID();
    this.syncedGeneration = null;
    this.historyAttempts = 0;
    this.touch(null);
  }

  markSynced() {
    this.lastHistoryEvent = new Date().toISOString();
    this.syncedGeneration = this.generation;
    if (!this.synced) {
      this.synced = true;
      this.touch(null);
    }
  }

  recordHistory(event) {
    this.lastHistoryEvent = new Date().toISOString();
    this.historyEvents.push({ at: this.lastHistoryEvent, generation: this.generation, ...event });
    if (this.historyEvents.length > 20) this.historyEvents.shift();
    this.touch(null);
  }

  markPartial() {
    this.generation = randomUUID();
    this.syncedGeneration = null;
    this.synced = false;
    this.touch(null);
  }

  entry(c) {
    return {
      chat_id: c.jid,
      name: this.nameOf(c.jid),
      unread: c.unread,
      is_group: c.isGroup,
      last_ts: c.lastTs,
      last_text: c.lastText,
      last_sender: c.lastSender,
      last_from_me: c.lastFromMe
    };
  }

  /** Every chat with unread messages plus the most recent ones (what Python stores). */
  snapshot(limit = 300) {
    const all = [...this.chats.values()].sort((a, b) => b.lastTs - a.lastTs);
    const unread = all.filter((c) => c.unread > 0);
    const recent = all.filter((c) => c.unread === 0).slice(0, Math.max(0, limit - unread.length));
    const chats = [...unread, ...recent].map((c) => this.entry(c));
    const direct = all.filter((c) => !c.isGroup);
    const events = [this.lastHistoryEvent, this.lastChatStateEvent, this.lastMessageEvent].filter(Boolean);
    return {
      synced: this.synced && this.syncedGeneration === this.generation,
      full: true, generation: this.generation, synced_generation: this.syncedGeneration,
      last_history_event: this.lastHistoryEvent, last_chat_state_event: this.lastChatStateEvent,
      last_message_event: this.lastMessageEvent, store_age_seconds: this.storeAgeSeconds ?? null,
      last_event_at: events.length ? events.sort().at(-1) : null,
      history_events: this.historyEvents, chat_events: this.chatEvents,
      last_history_filter: this.lastHistoryFilter,
      counts: { chats: all.length, direct: direct.length, groups: all.length - direct.length,
        unread_direct_chats: direct.filter((c) => c.unread > 0).length,
        unread_direct_messages: direct.reduce((n, c) => n + c.unread, 0) }, chats
    };
  }

  touch(jid) {
    if (jid) this.dirty.add(jid);
    if (this.timer) return;
    this.timer = setTimeout(() => this.flush(), this.debounceMs);
    if (this.timer.unref) this.timer.unref();
  }

  flush() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    const changed = [...this.dirty].map((j) => this.chats.get(j)).filter(Boolean).map((c) => this.entry(c));
    this.dirty.clear();
    this.save();
    if (this.onChange) {
      try {
        this.onChange({ ...this.snapshot(), full: false, chats: changed });
      } catch (e) {}
    }
  }
}

module.exports = { ChatIndex, normJid, skipJid, toSeconds };
