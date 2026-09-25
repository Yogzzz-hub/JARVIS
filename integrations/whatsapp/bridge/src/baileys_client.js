/**
 * Baileys Transport Client Adapter for JARVIS EDGE.
 * Purely transport-layer I/O.
 * Does not contain AI, memory, system prompts, or shell commands.
 */

const path = require("path");
const fs = require("fs");
const pino = require("pino");
const { normalizeIncomingMessage } = require("./protocol");
const { saveMediaBuffer } = require("./media");
const { ConnectionState, ReconnectManager } = require("./reconnect");

// Optional dynamic import of Baileys in case environment is running in mock/test mode
let baileysModule = null;
try {
  baileysModule = require("@whiskeysockets/baileys");
} catch (e) {
  // Will log or gracefully handle if baileys is not installed yet
}

class BaileysClient {
  constructor({
    authDir,
    tempDir,
    onNormalizedMessage = null,
    onStatusChange = null,
    onQrCode = null
  }) {
    this.authDir = authDir || path.resolve(__dirname, "../../../data/whatsapp_auth");
    this.tempDir = tempDir || path.resolve(__dirname, "../../../data/whatsapp_temp");
    this.pairingNumber = process.env.WHATSAPP_PHONE_NUMBER || "916381456199";
    this.onNormalizedMessage = onNormalizedMessage;
    this.onStatusChange = onStatusChange;
    this.onQrCode = onQrCode;
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

    try {
      this.sock = makeWASocket({
        auth: state,
        logger: this.logger,
        printQRInTerminal: false,
        syncFullHistory: false,
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
      }
    });

    this.sock.ev.on("messages.upsert", async ({ messages, type }) => {
      if (type !== "notify") return;

      for (const rawMsg of messages) {
        // Skip messages sent by oneself unless explicitly configured
        if (rawMsg.key?.fromMe) continue;

        let mediaRef = null;
        const msgType = Object.keys(rawMsg.message || {})[0];

        if (
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

        if (rawMsg.key && rawMsg.key.id && rawMsg.message) {
          this.saveMessage(rawMsg.key.id, rawMsg.message);
        }

        const normalized = normalizeIncomingMessage(rawMsg, mediaRef);
        if (normalized && this.onNormalizedMessage) {
          this.onNormalizedMessage(normalized);
        }
      }
    });

    return true;
  }

  async sendTextMessage(toJid, text, quoted = null) {
    if (!this.sock) {
      throw new Error("Baileys socket is not connected");
    }

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
  BaileysClient
};
