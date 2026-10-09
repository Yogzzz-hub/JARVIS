/** Temporary opt-in metadata-only boundary trace. Never writes message bodies. */
const fs = require("fs");

const allowed = new Set([
  "stage", "event_type", "message_id", "chat_jid", "from_me", "participant",
  "message_type", "timestamp", "generation", "upsert_type", "message_count",
  "normalization_result", "ws_dispatch_result", "python_receive_result",
  "sqlite_result", "reason", "connected_client_count"
]);

function traceIncoming(fields) {
  const file = process.env.JARVIS_WHATSAPP_TRACE_NODE;
  if (!file) return;
  const record = { at: new Date().toISOString() };
  for (const [key, value] of Object.entries(fields || {})) {
    if (allowed.has(key) && value !== undefined && value !== null) record[key] = value;
  }
  try { fs.appendFileSync(file, JSON.stringify(record) + "\n", { encoding: "utf8", mode: 0o600 }); }
  catch (_) { /* diagnostics must never interrupt ingestion */ }
}

module.exports = { traceIncoming };
