/**
 * JARVIS WhatsApp Bridge - Main Transport Service.
 * Connects WhatsApp (via Baileys) with the local Python JARVIS backend over WebSockets.
 * Strictly transport only: No LLMs, no Ollama, no prompt logic, no shell commands.
 */

const { WebSocketServer, WebSocket } = require("ws");
const { BaileysClient } = require("./baileys_client");
const { ConnectionState } = require("./reconnect");

const PORT = parseInt(process.env.JARVIS_WHATSAPP_PORT || "8768", 10);
const HOST = process.env.JARVIS_WHATSAPP_HOST || "127.0.0.1";

let activeJarvisSocket = null;
let lastQrCode = null;
let lastPairingCode = null;
// Messages that arrive while JARVIS (Python) is not connected are kept and delivered when it connects.
const MAX_PENDING = 500;
const pendingMessages = [];

const baileys = new BaileysClient({
  onNormalizedMessage: (normalizedMsg) => {
    broadcastToJarvis({
      type: "incoming_message",
      payload: normalizedMsg
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
  if (activeJarvisSocket && activeJarvisSocket.readyState === WebSocket.OPEN) {
    try {
      activeJarvisSocket.send(JSON.stringify(eventObj));
      return;
    } catch (e) {
      console.error("[Bridge] Failed to send to Jarvis:", e.message);
    }
  }
  if (eventObj.type === "incoming_message") {
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
      ws.send(JSON.stringify(event));
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
  console.log("[WhatsApp Bridge] Jarvis Python backend connected.");
  activeJarvisSocket = ws;

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
  ws.send(JSON.stringify({ type: "chat_state", payload: baileys.getChats() }));
  flushPending(ws);

  ws.on("message", async (data) => {
    try {
      const msg = JSON.parse(data.toString());
      const { id, action, payload } = msg;

      if (action === "connect") {
        const ok = await baileys.start();
        ws.send(JSON.stringify({ id, action, success: ok }));
      } else if (action === "disconnect") {
        await baileys.disconnect();
        ws.send(JSON.stringify({ id, action, success: true }));
      } else if (action === "send_text") {
        const { to, text, quoted } = payload;
        const res = await baileys.sendTextMessage(to, text, quoted);
        ws.send(JSON.stringify({ id, action, success: true, result: res }));
      } else if (action === "send_media") {
        const { to, file_path, mimetype, caption, is_voice_note } = payload;
        const res = await baileys.sendMediaMessage(to, file_path, mimetype, caption, is_voice_note);
        ws.send(JSON.stringify({ id, action, success: true, result: res }));
      } else if (action === "get_message") {
        // Bounded retry for messages that arrived undecrypted: return the body only once it exists.
        const found = baileys.getNormalizedMessage((payload || {}).message_id);
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
