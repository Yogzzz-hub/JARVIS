/**
 * Protocol Translation Layer for JARVIS WhatsApp Bridge.
 * Normalizes raw Baileys events into typed Jarvis message objects.
 * Transport-only: Zero AI intelligence or prompt generation.
 */

// WAMessageStubType.CIPHERTEXT: the message arrived but could not be decrypted yet
// (WhatsApp shows "Waiting for this message. This may take a while.").
const STUB_CIPHERTEXT = 2;

function isGroupJid(jid) {
  return String(jid || "").endsWith("@g.us");
}

function isDirectJid(jid) {
  return /@(s\.whatsapp\.net|lid|c\.us)$/.test(String(jid || ""));
}

/**
 * Placeholder event for a message whose body is not available yet. Python never replies to it;
 * the real body arrives later (messages.upsert / messages.update) with the same message_id.
 */
function normalizePendingMessage(rawMsg) {
  const key = (rawMsg && rawMsg.key) || {};
  if (!key.id || !key.remoteJid || !(isDirectJid(key.remoteJid) || isGroupJid(key.remoteJid))) return null;
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

function normalizeIncomingMessage(rawMsg, downloadedMediaRef = null, onDecision = null) {
  const decision = (result, reason, messageType = "") => {
    if (onDecision) onDecision({ result, reason, messageType });
  };
  if (!rawMsg || !rawMsg.message) {
    decision("REJECTED", "EMPTY_BODY");
    return null;
  }

  const key = rawMsg.key || {};
  if (!key.id || !key.remoteJid) {
    decision("REJECTED", !key.id ? "MISSING_MESSAGE_ID" : "MISSING_CHAT_JID");
    return null;
  }
  const messageId = key.id;
  const chatId = key.remoteJid || "";
  if (!(isDirectJid(chatId) || isGroupJid(chatId))) {
    decision("REJECTED", "NON_CHAT_CHANNEL");
    return null;
  }
  const isFromMe = Boolean(key.fromMe);
  const senderId = key.participant || (isFromMe ? "me" : key.remoteJid) || "";
  const displayName = rawMsg.pushName || senderId.split("@")[0] || "Unknown";
  const timestamp = new Date(
    rawMsg.messageTimestamp ? Number(rawMsg.messageTimestamp) * 1000 : Date.now()
  ).toISOString();

  // Ephemeral wrappers retain their expiration metadata; view-once is not unwrapped.
  const msg = rawMsg.message.ephemeralMessage?.message || rawMsg.message;
  let type = "text";
  let text = "";
  let mediaRef = downloadedMediaRef;
  let replyTo = null;

  // Extract contextual reply if present
  const contextInfo =
    msg.extendedTextMessage?.contextInfo ||
    msg.imageMessage?.contextInfo ||
    msg.documentMessage?.contextInfo ||
    msg.audioMessage?.contextInfo || msg.videoMessage?.contextInfo;

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
  } else if (msg.videoMessage) {
    type = "video"; text = msg.videoMessage.caption || "";
  } else if (msg.stickerMessage) {
    type = "sticker";
  } else if (msg.locationMessage || msg.liveLocationMessage) {
    type = "location"; text = (msg.locationMessage || msg.liveLocationMessage).name || "";
  } else if (msg.contactMessage || msg.contactsArrayMessage) {
    type = "contact"; text = (msg.contactMessage || msg.contactsArrayMessage).displayName || "";
  } else if (msg.reactionMessage) {
    type = "reaction"; text = msg.reactionMessage.text || "";
    replyTo = { message_id: msg.reactionMessage.key?.id || "", participant: msg.reactionMessage.key?.participant || null };
  } else if (msg.pollCreationMessage || msg.pollCreationMessageV2 || msg.pollCreationMessageV3) {
    type = "poll"; text = (msg.pollCreationMessage || msg.pollCreationMessageV2 || msg.pollCreationMessageV3).name || "";
  } else if (msg.eventMessage) {
    type = "event"; text = msg.eventMessage.name || "";
  } else {
    // Unrecognized or unsupported message type (reaction, sticker, protocol)
    decision("REJECTED", "UNSUPPORTED_MESSAGE_TYPE", Object.keys(msg || {})[0] || "unknown");
    return null;
  }

  const mediaBody = msg.imageMessage || msg.documentMessage || msg.audioMessage || msg.videoMessage || msg.stickerMessage;
  if (mediaBody) {
    mediaRef = { filename: mediaBody.fileName || type, mimetype: mediaBody.mimetype || "application/octet-stream",
      size_bytes: Number(mediaBody.fileLength || 0), downloaded: false, ...(mediaRef || {}) };
  }

  decision("ACCEPTED", "", type);
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
    state: "READY",
    metadata: { ephemeral_expiration: contextInfo?.expiration || null,
      location: msg.locationMessage || msg.liveLocationMessage || null,
      contact: msg.contactMessage || msg.contactsArrayMessage || null,
      poll: msg.pollCreationMessage || msg.pollCreationMessageV2 || msg.pollCreationMessageV3 || null,
      event: msg.eventMessage || null }
  };
}

module.exports = {
  normalizeIncomingMessage,
  normalizePendingMessage,
  isPendingDecryption,
  isGroupJid
};
