/**
 * Protocol Translation Layer for JARVIS WhatsApp Bridge.
 * Normalizes raw Baileys events into typed Jarvis message objects.
 * Transport-only: Zero AI intelligence or prompt generation.
 */

// WAMessageStubType.CIPHERTEXT: the message arrived but could not be decrypted yet
// (WhatsApp shows "Waiting for this message. This may take a while.").
const STUB_CIPHERTEXT = 2;

function isGroupJid(jid) {
  return /@(g\.us|broadcast|newsletter)$/.test(jid || "") || String(jid || "").startsWith("status@");
}

/**
 * Placeholder event for a message whose body is not available yet. Python never replies to it;
 * the real body arrives later (messages.upsert / messages.update) with the same message_id.
 */
function normalizePendingMessage(rawMsg) {
  const key = (rawMsg && rawMsg.key) || {};
  if (!key.id || !key.remoteJid) return null;
  const isFromMe = Boolean(key.fromMe);
  const senderId = key.participant || (isFromMe ? "me" : key.remoteJid) || "";
  return {
    channel: "whatsapp",
    message_id: key.id,
    chat_id: key.remoteJid,
    sender_id: senderId,
    sender_display_name: rawMsg.pushName || senderId.split("@")[0] || "Unknown",
    timestamp: new Date(rawMsg.messageTimestamp ? Number(rawMsg.messageTimestamp) * 1000 : Date.now()).toISOString(),
    type: "text",
    text: "",
    media_ref: null,
    reply_to: null,
    is_from_me: isFromMe,
    is_group: isGroupJid(key.remoteJid),
    state: "PENDING_DECRYPTION"
  };
}

function isPendingDecryption(rawMsg) {
  if (!rawMsg || !rawMsg.key) return false;
  // other stub events (missed calls, security notices) carry no body and are not pending messages
  return rawMsg.messageStubType === STUB_CIPHERTEXT || (!rawMsg.message && !rawMsg.messageStubType);
}

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
    is_from_me: isFromMe,
    is_group: isGroupJid(chatId),
    state: "READY"
  };
}

module.exports = {
  normalizeIncomingMessage,
  normalizePendingMessage,
  isPendingDecryption,
  isGroupJid
};
