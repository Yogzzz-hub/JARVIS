/**
 * Protocol Translation Layer for JARVIS WhatsApp Bridge.
 * Normalizes raw Baileys events into typed Jarvis message objects.
 * Transport-only: Zero AI intelligence or prompt generation.
 */

function normalizeIncomingMessage(rawMsg, downloadedMediaRef = null) {
  if (!rawMsg || !rawMsg.message) {
    return null;
  }

  const key = rawMsg.key || {};
  const messageId = key.id || `msg_${Date.now()}`;
  const chatId = key.remoteJid || "";
  const isFromMe = Boolean(key.fromMe);
  const senderId = key.participant || (isFromMe ? "me" : key.remoteJid) || "";
  const displayName = rawMsg.pushName || senderId.split("@")[0] || "Unknown";
  const timestamp = new Date(
    rawMsg.messageTimestamp ? Number(rawMsg.messageTimestamp) * 1000 : Date.now()
  ).toISOString();

  const msg = rawMsg.message;
  let type = "text";
  let text = "";
  let mediaRef = downloadedMediaRef;
  let replyTo = null;

  // Extract contextual reply if present
  const contextInfo =
    msg.extendedTextMessage?.contextInfo ||
    msg.imageMessage?.contextInfo ||
    msg.documentMessage?.contextInfo ||
    msg.audioMessage?.contextInfo;

  if (contextInfo && contextInfo.stanzaId) {
    replyTo = {
      message_id: contextInfo.stanzaId,
      participant: contextInfo.participant || null,
      quoted_text: contextInfo.quotedMessage?.conversation || null
    };
  }

  if (msg.conversation) {
    type = "text";
    text = msg.conversation;
  } else if (msg.extendedTextMessage) {
    type = "text";
    text = msg.extendedTextMessage.text || "";
  } else if (msg.imageMessage) {
    type = "image";
    text = msg.imageMessage.caption || "";
  } else if (msg.documentMessage) {
    type = "document";
    text = msg.documentMessage.caption || msg.documentMessage.fileName || "";
  } else if (msg.audioMessage) {
    type = msg.audioMessage.ptt ? "voice_note" : "audio";
    text = "";
  } else {
    // Unrecognized or unsupported message type (reaction, sticker, protocol)
    return null;
  }

  return {
    channel: "whatsapp",
    message_id: messageId,
    chat_id: chatId,
    sender_id: senderId,
    sender_display_name: displayName,
    timestamp: timestamp,
    type: type,
    text: text.trim(),
    media_ref: mediaRef,
    reply_to: replyTo,
    is_from_me: isFromMe
  };
}

module.exports = {
  normalizeIncomingMessage
};
