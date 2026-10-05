/**
 * JARVIS WhatsApp Bridge - Main Transport Service.
 * Connects WhatsApp (via Baileys) with the local Python JARVIS backend over WebSockets.
 * Strictly transport only: No LLMs, no Ollama, no prompt logic, no shell commands.
 */

const { WebSocketServer, WebSocket } = require("ws");
const { BaileysClient } = require("./baileys_client");
const { ConnectionState } = require("./reconnect");
const { traceIncoming } = require("./incoming_trace");
const { createOneShotGate } = require("./outgoing_guard");

const PORT = parseInt(process.env.JARVIS_WHATSAPP_PORT || "8768", 10);
const HOST = process.env.JARVIS_WHATSAPP_HOST || "127.0.0.1";
const READ_ONLY = process.env.JARVIS_WHATSAPP_READ_ONLY === "1";
const oneShot = createOneShotGate({
  to: process.env.JARVIS_WHATSAPP_ONE_SHOT_TO || "",
  text: process.env.JARVIS_WHATSAPP_ONE_SHOT_TEXT || "",
  requestId: process.env.JARVIS_WHATSAPP_ONE_SHOT_REQUEST_ID || ""
});
// libsignal may log session objects with key material through console.
for (const method of ["log", "warn", "error", "info"]) {
  const original = console[method].bind(console);
  console[method] = (...args) => {
    if (args.some((arg) => typeof arg === "object" && arg !== null)) return;
    original(...args);
  };
}

let activeJarvisSocket = null;
let lastQrCode = null;
let lastPairingCode = null;
// Messages that arrive while JARVIS (Python) is not connected are kept and delivered when it connects.
const MAX_PENDING = 500;
const pendingMessages = [];

const baileys = new BaileysClient({
  onNormalizedMessage: (normalizedMsg) => {
    traceIncoming({ stage: "bridge_callback", event_type: "incoming_message",
      message_id: normalizedMsg.message_id, chat_jid: normalizedMsg.chat_id,
      from_me: normalizedMsg.is_from_me, message_type: normalizedMsg.type,
      timestamp: normalizedMsg.timestamp, generation: baileys.chatIndex.generation,
      normalization_result: normalizedMsg.state });
    broadcastToJarvis({
      type: "incoming_message",
      payload: normalizedMsg,
      generation: baileys.chatIndex.generation
    });
  },
  onStatusChange: (state, meta) => {
    broadcastToJarvis({
      type: "status_update",
      payload: {
        state,
        meta,
        timestamp: new Date().toISOString()
      }
    });
  },
  onRuntimeUpdate: (status, chats) => {
    broadcastToJarvis({ type: "status_update", payload: status });
    broadcastToJarvis({ type: "chat_state", payload: chats });
  },
  onQrCode: (qr) => {
    lastQrCode = qr;
    broadcastToJarvis({
      type: "qr_code",
      payload: { qr }
    });
  },
  onChatState: (state) => {
    broadcastToJarvis({ type: "chat_state", payload: state });
  }
});

baileys.onPairingCode = (code) => {
  lastPairingCode = code;
  broadcastToJarvis({
    type: "pairing_code",
    payload: { code }
  });
};

function broadcastToJarvis(eventObj) {
  const payload = eventObj.payload || {};
  const traceDispatch = (result, reason = "") => {
    if (eventObj.type !== "incoming_message") return;
    traceIncoming({ stage: "websocket_dispatch", event_type: eventObj.type,
      message_id: payload.message_id, chat_jid: payload.chat_id, from_me: payload.is_from_me,
      message_type: payload.type, timestamp: payload.timestamp,
      generation: eventObj.generation, connected_client_count:
        activeJarvisSocket?.readyState === WebSocket.OPEN ? 1 : 0,
      ws_dispatch_result: result, reason });
  };
  if (activeJarvisSocket && activeJarvisSocket.readyState === WebSocket.OPEN) {
    try {
      activeJarvisSocket.send(JSON.stringify(eventObj), (error) =>
        traceDispatch(error ? "WRITE_FAILED" : "WRITE_ACCEPTED", error ? "SOCKET_SEND_ERROR" : ""));
      return;
    } catch (e) {
      traceDispatch("WRITE_FAILED", "SOCKET_SEND_THROW");
      console.error("[Bridge] Failed to send to Jarvis:", e.message);
    }
  }
  if (eventObj.type === "incoming_message") {
    traceDispatch("QUEUED", "NO_ACTIVE_PYTHON_CLIENT");
    pendingMessages.push({ event: eventObj, at: Date.now() });
    if (pendingMessages.length > MAX_PENDING) pendingMessages.shift();
  }
}

/** Deliver what arrived while JARVIS was away. Anything older than two minutes is history: stored, never acted on. */
function flushPending(ws) {
  while (pendingMessages.length) {
    const { event, at } = pendingMessages.shift();
    if (Date.now() - at > 120 * 1000) event.payload = { ...event.payload, history: true };
    try {
      ws.send(JSON.stringify(event), (error) => {
        const payload = event.payload || {};
        traceIncoming({ stage: "websocket_dispatch", event_type: event.type,
          message_id: payload.message_id, chat_jid: payload.chat_id, from_me: payload.is_from_me,
          message_type: payload.type, timestamp: payload.timestamp,
          generation: event.generation, connected_client_count: 1,
          ws_dispatch_result: error ? "FLUSH_FAILED" : "FLUSH_ACCEPTED" });
      });
    } catch (e) {
      pendingMessages.unshift({ event, at });
      return;
    }
  }
}

const wss = new WebSocketServer({ host: HOST, port: PORT });

console.log(`[WhatsApp Bridge] Transport server listening on ws://${HOST}:${PORT}`);

// Auto-start Baileys client so QR / Pairing code generates right away
baileys.start().catch((err) => {
  console.error("[WhatsApp Bridge] Initial Baileys start info:", err.message);
});

wss.on("connection", (ws, req) => {
  if (req.url === "/diagnostics") {
    ws.send(JSON.stringify({ type: "status_update", payload: baileys.getStatus() }));
    ws.close();
    return;
  }
  const commandOnly = req.url === "/commands";
  if (!commandOnly && activeJarvisSocket?.readyState === WebSocket.OPEN) {
    ws.close(1013, "Backend already connected; use /diagnostics for read-only status");
    return;
  }
  if (!commandOnly) {
    console.log("[WhatsApp Bridge] Jarvis Python backend connected.");
    activeJarvisSocket = ws;
  }

  // Send current status immediately upon connection
  ws.send(
    JSON.stringify({
      type: "status_update",
      payload: {
        ...baileys.getStatus(),
        qr: lastQrCode,
        timestamp: new Date().toISOString()
      }
    })
  );
  // WhatsApp's unread badges as they are now, then the messages that came in meanwhile.
  if (!commandOnly) {
    ws.send(JSON.stringify({ type: "chat_state", payload: baileys.getChats() }));
    flushPending(ws);
  }

  ws.on("message", async (data) => {
    try {
      const msg = JSON.parse(data.toString());
      const { id, action, payload } = msg;

      if (READ_ONLY && ["send_text", "send_media"].includes(action) &&
          !oneShot.consume({ commandOnly, id, action, payload })) {
        ws.send(JSON.stringify({ id, action, success: false, error: "Read-only mode" }));
        return;
      }

      if (action === "connect") {
        const ok = await baileys.start();
        ws.send(JSON.stringify({ id, action, success: ok }));
      } else if (action === "disconnect") {
        await baileys.disconnect();
        ws.send(JSON.stringify({ id, action, success: true }));
      } else if (action === "send_text") {
        const { to, text, quoted } = payload;
        const res = await baileys.sendTextMessage(to, text, quoted);
        baileys.eventHealth.last_outgoing_command = { request_id: id, action, status: res.status, message_id: res.message_id };
        ws.send(JSON.stringify({ id, action, success: true, result: res }));
      } else if (action === "send_media") {
        const { to, file_path, mimetype, caption, is_voice_note } = payload;
        const res = await baileys.sendMediaMessage(to, file_path, mimetype, caption, is_voice_note);
        ws.send(JSON.stringify({ id, action, success: true, result: res }));
      } else if (action === "get_message") {
        // Bounded retry for messages that arrived undecrypted: return the body only once it exists.
        const found = await baileys.getMessageWithMedia((payload || {}).message_id, (payload || {}).chat_id, Boolean((payload || {}).download));
        ws.send(JSON.stringify({ id, action, success: Boolean(found), result: found }));
      } else if (action === "get_chats") {
        ws.send(JSON.stringify({ id, action, success: true, result: baileys.getChats() }));
      } else if (action === "get_status") {
        ws.send(JSON.stringify({ id, action, success: true, result: baileys.getStatus() }));
      } else if (action === "ping") {
        ws.send(JSON.stringify({ id, action: "pong" }));
      } else {
        ws.send(JSON.stringify({ id, action, success: false, error: `Unknown action: ${action}` }));
      }
    } catch (err) {
      console.error("[WhatsApp Bridge] Command handling error:", err);
      let parsedId = null;
      let parsedAction = "error";
      try {
        const parsed = JSON.parse(data.toString());
        parsedId = parsed?.id;
        parsedAction = parsed?.action || "error";
      } catch (e) {}
      ws.send(
        JSON.stringify({
          id: parsedId,
          action: parsedAction,
          success: false,
          status: err.outcomeUnknown ? "UNCERTAIN" : "FAILED",
          error: err.message
        })
      );
    }
  });

  ws.on("close", () => {
    console.log("[WhatsApp Bridge] Jarvis backend disconnected.");
    if (activeJarvisSocket === ws) {
      activeJarvisSocket = null;
    }
  });
});

process.on("SIGINT", async () => {
  console.log("[WhatsApp Bridge] Shutting down transport bridge...");
  await baileys.disconnect();
  wss.close();
  process.exit(0);
});

module.exports = {
  baileys,
  wss
};
