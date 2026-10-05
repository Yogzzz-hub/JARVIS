/** Read-only live Baileys listener using a COPY of auth. No bridge, Python, or chat sends. */
const fs = require("fs");
const path = require("path");
const pino = require("pino");
const baileys = require(process.env.WA_PROBE_MODULE || "@whiskeysockets/baileys");
// libsignal writes session key objects to console; permit only our explicit JSON records.
const output = (value) => process.stdout.write(JSON.stringify(value) + "\n");
console.log = console.info = console.warn = console.error = () => {};

const authDir = process.env.WA_PROBE_AUTH_DIR;
if (!authDir || !path.isAbsolute(authDir) || !fs.existsSync(path.join(authDir, "creds.json")))
  throw new Error("WA_PROBE_AUTH_DIR must be an absolute copied-auth directory");
const events = ["messages.upsert", "messages.update", "messages.delete", "message-receipt.update",
  "chats.upsert", "chats.update", "contacts.update", "presence.update", "connection.update",
  "messaging-history.set", "messaging-history.status"];
const result = { counts: Object.fromEntries(events.map((name) => [name, 0])),
  event_map_counts: {}, pending: null, open_at: null, listener_registered_at: null,
  buffer_active: false, buffer_started_at: null, buffer_released_at: null,
  raw_messages_upsert: 0, raw_by_jid_type: {}, raw_after_open: 0,
  processed_messages_upsert: 0, jid_type: null,
  is_online: null, last_disconnect_code: null, presence_error: null,
  nodes: {}, offline_values: {}, acks: {}, offline_nodes: 0, preview_nodes: 0 };
const typeOf = (jid) => jid?.endsWith("@lid") ? "LID" : jid?.endsWith("@s.whatsapp.net") ? "PN" :
  jid?.endsWith("@g.us") ? "group" : jid?.endsWith("@newsletter") ? "newsletter" :
  jid?.endsWith("@broadcast") ? "broadcast" : "other";

async function main() {
  const { state, saveCreds } = await baileys.useMultiFileAuthState(authDir);
  const sock = baileys.default({ auth: state, logger: pino({ level: "silent" }),
    printQRInTerminal: false, syncFullHistory: false, markOnlineOnConnect: false,
    shouldSyncHistoryMessage: () => false, getMessage: async () => undefined });
  const ev = sock.ev;
  sock.ws.on('CB:message', node => {
    const kind = typeOf(node.attrs.from);
    result.nodes[kind] = (result.nodes[kind] || 0) + 1;
    const offline = String(node.attrs.offline ?? 'absent');
    result.offline_values[offline] = (result.offline_values[offline] || 0) + 1;
  });
  sock.ws.on('CB:ib,,offline', () => result.offline_nodes++);
  sock.ws.on('CB:ib,,offline_preview', () => result.preview_nodes++);
  const emit = ev.emit.bind(ev);
  ev.emit = (name, payload) => {
    if (name === "messages.upsert") {
      result.raw_messages_upsert += (payload?.messages || []).length;
      result.jid_type = typeOf(payload?.messages?.[0]?.key?.remoteJid);
      for (const message of payload?.messages || []) {
        const kind = typeOf(message?.key?.remoteJid);
        result.raw_by_jid_type[kind] = (result.raw_by_jid_type[kind] || 0) + 1;
        if (result.open_at) result.raw_after_open += 1;
      }
    }
    return emit(name, payload);
  };
  const buffer = ev.buffer.bind(ev);
  ev.buffer = (...args) => { result.buffer_active = true; result.buffer_started_at = new Date().toISOString(); return buffer(...args); };
  const flush = ev.flush.bind(ev);
  ev.flush = (...args) => { const released = flush(...args);
    if (released) { result.buffer_active = false; result.buffer_released_at = new Date().toISOString(); }
    return released; };
  ev.process((map) => { for (const name of Object.keys(map))
    result.event_map_counts[name] = (result.event_map_counts[name] || 0) + 1; });
  for (const name of events) ev.on(name, (payload) => {
    result.counts[name] += 1;
    if (name === "messages.upsert") result.processed_messages_upsert += (payload?.messages || []).length;
    if (name === "connection.update") {
      if (Object.hasOwn(payload, "receivedPendingNotifications")) result.pending = payload.receivedPendingNotifications;
      if (Object.hasOwn(payload, "isOnline")) result.is_online = payload.isOnline;
      if (payload.connection === "open") {
        result.open_at = new Date().toISOString();
        sock.sendPresenceUpdate("unavailable").catch((err) => { result.presence_error = String(err?.message || err); });
        output({ phase: "OPEN", ...result });
      }
      if (payload.connection === "close") result.last_disconnect_code = payload.lastDisconnect?.error?.output?.statusCode ?? null;
    }
  });
  ev.on("creds.update", saveCreds);
  result.listener_registered_at = new Date().toISOString();
  const snapshot = phase => ({ phase, ...result, buffer_active: ev.isBuffering() });
  setInterval(() => output(snapshot("SAMPLE")), 15000).unref();
  setTimeout(() => { output(snapshot("END"));
    try { sock.end(new Error("probe complete")); } catch (_) {}
    process.exit(0);
  }, Number(process.env.WA_PROBE_TIMEOUT_MS) || 75000);
}
main().catch((err) => { output({ fatal: String(err?.message || err) }); process.exit(1); });
