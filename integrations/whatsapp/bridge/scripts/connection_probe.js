/** Minimal, bounded Baileys connection probe. Use only with a COPY of auth while the bridge is stopped.
 * No sendMessage, JARVIS socket, chat store, or auto-reply code is loaded.
 */
const fs = require("fs");
const path = require("path");
const pino = require("pino");
const baileys = require("@whiskeysockets/baileys");

const authDir = process.env.WA_PROBE_AUTH_DIR;
if (!authDir || !path.isAbsolute(authDir) || !fs.existsSync(path.join(authDir, "creds.json"))) {
  throw new Error("WA_PROBE_AUTH_DIR must point to an existing copied auth directory");
}
const timeoutMs = Math.max(5000, Math.min(Number(process.env.WA_PROBE_TIMEOUT_MS) || 25000, 30000));
const afterOpenMs = Math.max(1000, Math.min(Number(process.env.WA_PROBE_AFTER_OPEN_MS) || 3000, 20000));
const mode = process.env.WA_PROBE_MODE || "default";
const versionText = process.env.WA_PROBE_VERSION || "";
const version = versionText ? versionText.split(".").map(Number) : undefined;
if (version && (version.length !== 3 || version.some((x) => !Number.isInteger(x)))) {
  throw new Error("WA_PROBE_VERSION must be a three-part numeric version");
}

function safeError(err) {
  const message = String(err?.message || "").replace(/[A-Za-z0-9_-]{40,}/g, "[redacted]").slice(0, 180);
  const payload = err?.output?.payload || {};
  return { name: String(err?.name || ""), message, status_code: err?.output?.statusCode ?? null,
    boom_error: String(payload.error || "").slice(0, 80),
    boom_message: String(payload.message || "").replace(/[A-Za-z0-9_-]{40,}/g, "[redacted]").slice(0, 120),
    stack_prefix: String(err?.stack || "").split("\n").slice(0, 2).join(" | ").slice(0, 220) };
}

async function main() {
  const logger = pino({ level: "silent" });
  const { state, saveCreds } = await baileys.useMultiFileAuthState(authDir);
  const started = Date.now();
  const result = { mode, version: version || baileys.DEFAULT_CONNECTION_CONFIG.version,
    browser: baileys.DEFAULT_CONNECTION_CONFIG.browser, registered: Boolean(state.creds?.registered),
    open: false, time_to_open_ms: null, time_to_close_ms: null, status_code: null,
    history_events: 0, history_chats: 0, history_messages: 0, chat_events: 0, message_events: 0,
    creds_update_events: 0, creds_write_success: 0, creds_write_error: 0, updates: [], error: null };
  const auth = mode === "cacheable"
    ? { creds: state.creds, keys: baileys.makeCacheableSignalKeyStore(state.keys, logger) }
    : state;
  const config = { auth, logger, printQRInTerminal: false, syncFullHistory: false,
    shouldSyncHistoryMessage: (msg) => [0, 3, 4, 6].includes(msg?.syncType),
    getMessage: async () => undefined };
  if (version) config.version = version;
  if (mode === "no_presence") config.markOnlineOnConnect = false;
  const sock = baileys.default(config);
  let finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    console.log(JSON.stringify(result));
    try { sock.end(new Error("diagnostic probe complete")); } catch (e) {}
    setTimeout(() => process.exit(0), 150).unref();
  };
  const timer = setTimeout(finish, timeoutMs);
  sock.ev.on("creds.update", async () => {
    result.creds_update_events++;
    try { await saveCreds(); result.creds_write_success++; }
    catch (e) { result.creds_write_error++; }
  });
  sock.ev.on("messaging-history.set", ({ chats, messages }) => {
    result.history_events++; result.history_chats += (chats || []).length;
    result.history_messages += (messages || []).length;
  });
  sock.ev.on("chats.upsert", (chats) => { result.chat_events += (chats || []).length; });
  sock.ev.on("chats.update", (chats) => { result.chat_events += (chats || []).length; });
  sock.ev.on("messages.upsert", ({ messages }) => { result.message_events += (messages || []).length; });
  sock.ev.on("connection.update", ({ connection, lastDisconnect, receivedPendingNotifications, isNewLogin, qr }) => {
    result.updates.push({ at_ms: Date.now() - started, connection: connection || null,
      received_pending_notifications: receivedPendingNotifications ?? null,
      is_new_login: isNewLogin ?? null, qr_present: Boolean(qr) });
    if (connection === "open") {
      result.open = true; result.time_to_open_ms = Date.now() - started;
      clearTimeout(timer);
      setTimeout(finish, afterOpenMs).unref();
    } else if (connection === "close") {
      result.time_to_close_ms = Date.now() - started;
      result.error = safeError(lastDisconnect?.error);
      result.status_code = result.error.status_code;
      clearTimeout(timer); finish();
    }
  });
}
main().catch((err) => { console.log(JSON.stringify({ fatal: safeError(err) })); process.exit(1); });
