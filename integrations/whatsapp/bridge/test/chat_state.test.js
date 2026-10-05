/**
 * Unread badges and missed messages: runs without WhatsApp (node --test integrations/whatsapp/bridge/test).
 */
const test = require("node:test");
const assert = require("node:assert");
const os = require("os");
const path = require("path");
const fs = require("fs");
const { EventEmitter } = require("events");
const Module = require("module");

// Only the logger is needed from the bridge's npm packages; stub it when they are not installed.
try {
  require.resolve("pino");
} catch (e) {
  const load = Module._load;
  Module._load = function (request, ...rest) {
    return request === "pino" ? () => ({}) : load.call(this, request, ...rest);
  };
}

const { ChatIndex } = require("../src/chat_index");
const { BaileysClient } = require("../src/baileys_client");

const ME = "916381456199@s.whatsapp.net";
const ASHOK = "919000000001@s.whatsapp.net";
const SANJANA = "919000000002@s.whatsapp.net";
const GROUP = "120363000000000001@g.us";
const now = () => Math.floor(Date.now() / 1000);

test("chat deltas carry the current generation and event metadata", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wa-delta-"));
  const updates = [];
  const index = new ChatIndex(path.join(dir, "chats.json"), { onChange: state => updates.push(state) });
  index.lastMessageEvent = new Date().toISOString();
  index.applyChats([{ id: "123@lid", unreadCount: 1 }], { absolute: true });
  index.flush();
  const delta = updates.at(-1);
  assert.equal(delta.generation, index.generation);
  assert.equal(delta.last_message_event, index.lastMessageEvent);
  assert.equal(delta.full, false);
  assert.equal(delta.counts.unread_direct_messages, 1);
});

function msg(id, chat, text, { fromMe = false, ts = now(), participant, pushName } = {}) {
  return { key: { id, remoteJid: chat, fromMe, participant }, message: { conversation: text }, messageTimestamp: ts, pushName };
}

function client() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "wa-bridge-"));
  const seen = [];
  const states = [];
  const c = new BaileysClient({ authDir: dir, tempDir: dir, onNormalizedMessage: (m) => seen.push(m), onChatState: (s) => states.push(s) });
  c.chatIndex.debounceMs = 5;
  const sock = { ev: new EventEmitter(), user: { id: "916381456199:7@s.whatsapp.net" } };
  c.sock = sock;
  c.bindEvents(sock, null);
  return { c, sock, seen, states, dir };
}

const tick = () => new Promise((r) => setTimeout(r, 30));

test("outgoing text requires a Baileys message ID and preserves LID recipients", async () => {
  const { c, sock } = client();
  const calls = [];
  sock.sendMessage = async (...args) => { calls.push(args); return {}; };
  assert.equal((await c.sendTextMessage("123@lid", "test")).status, "UNCERTAIN");
  sock.sendMessage = async (...args) => { calls.push(args); return { key: { id: "receipt-1" }, messageTimestamp: 123 }; };
  const result = await c.sendTextMessage("123@lid", "test");
  assert.equal(result.status, "SENT");
  assert.equal(result.message_id, "receipt-1");
  assert.equal(calls.length, 2);
  assert.equal(calls[0][0], "123@lid");
  assert.deepEqual(calls[0][1], { text: "test" });
});

test("outgoing socket rejection is uncertain and never retried", async () => {
  const { c, sock } = client();
  let calls = 0;
  sock.sendMessage = async () => { calls++; throw new Error("connection lost"); };
  await assert.rejects(c.sendTextMessage("123@lid", "test"), error => error.outcomeUnknown === true);
  assert.equal(calls, 1);
});

test("offline diagnostic uses one bounded control request and no chat send", async () => {
  const { c, sock } = client();
  const calls = [];
  sock.ws = { isOpen: true };
  sock.sendNode = async node => calls.push(node);
  sock.sendMessage = async () => assert.fail("must not send a chat message");
  await assert.rejects(c.probeOfflineBatch(10001));
  await c.probeOfflineBatch(1000);
  assert.deepEqual(calls, [{ tag: "ib", attrs: {}, content: [{ tag: "offline_batch", attrs: { count: "1000" } }] }]);
  await assert.rejects(c.probeOfflineBatch(1000));
  assert.equal(calls.length, 1);
});

test("offline completion republishes current runtime health and chat state", () => {
  const { c } = client();
  c.sock.ev.isBuffering = () => false;
  const updates = [];
  c.onRuntimeUpdate = (status, chats) => updates.push({ status, chats });
  c.notePendingNotifications(true);
  assert.equal(updates.length, 1);
  assert.equal(updates[0].status.event_health.received_pending_notifications, true);
  assert.equal(updates[0].chats.generation, c.chatIndex.generation);
});

test("history sync gives exact unread counts, names, and forwards the unread messages as history", async () => {
  const { c, sock, seen } = client();
  sock.ev.emit("messaging-history.set", {
    isLatest: true,
    chats: [
      { id: ASHOK, unreadCount: 1, conversationTimestamp: now() - 60 },
      { id: SANJANA, unreadCount: 2, conversationTimestamp: now() - 700 },
      { id: GROUP, name: "RIT SIH & Techgium 2026", unreadCount: 2, conversationTimestamp: now() - 30 },
      { id: "919000000003@s.whatsapp.net", unreadCount: 0, conversationTimestamp: now() - 9000 }
    ],
    contacts: [{ id: ASHOK, name: "Ashok Kumar" }, { id: SANJANA, notify: "Sanjana Ssk" }],
    messages: [
      msg("a1", ASHOK, "OK, I will check", { ts: now() - 60 }),
      msg("a0", ASHOK, "old and read", { ts: now() - 5000, fromMe: true }),
      msg("s1", SANJANA, "Hi", { ts: now() - 800 }),
      msg("s2", SANJANA, "Ena man panra", { ts: now() - 700 }),
      msg("g1", GROUP, "Meeting at 5", { ts: now() - 30, participant: "919000000009@s.whatsapp.net" })
    ]
  });
  const snap = c.getChats();
  assert.strictEqual(snap.synced, true);
  assert.strictEqual(snap.synced_generation, snap.generation);
  assert.ok(snap.last_history_event);
  const by = Object.fromEntries(snap.chats.map((x) => [x.chat_id, x]));
  assert.strictEqual(by[ASHOK].unread, 1);
  assert.strictEqual(by[ASHOK].name, "Ashok Kumar");
  assert.strictEqual(by[ASHOK].last_text, "OK, I will check");
  assert.strictEqual(by[SANJANA].unread, 2);
  assert.strictEqual(by[SANJANA].name, "Sanjana Ssk");
  assert.strictEqual(by[GROUP].name, "RIT SIH & Techgium 2026");
  assert.ok(by[GROUP].is_group);
  const ids = seen.map((m) => m.message_id).sort();
  assert.deepStrictEqual(ids, ["a1", "g1", "s1", "s2"]);
  assert.ok(seen.every((m) => m.history === true));
  assert.strictEqual(seen.find((m) => m.message_id === "g1").chat_name, "RIT SIH & Techgium 2026");
});

test("live counts: new messages add, the owner reading on the phone or replying clears", async () => {
  const { c, sock } = client();
  sock.ev.emit("chats.update", [{ id: ASHOK, unreadCount: 1 }]);
  sock.ev.emit("chats.update", [{ id: ASHOK, unreadCount: 2 }]);
  assert.strictEqual(c.chatIndex.chats.get(ASHOK).unread, 3);
  sock.ev.emit("chats.update", [{ id: ASHOK, unreadCount: null }]);
  assert.strictEqual(c.chatIndex.chats.get(ASHOK).unread, 3);
  // read receipt from the owner's phone ("read-self": not fromMe, status READ)
  sock.ev.emit("messages.update", [{ key: { remoteJid: ASHOK, id: "x", fromMe: false }, update: { status: 4 } }]);
  assert.strictEqual(c.chatIndex.chats.get(ASHOK).unread, 0);
  // the other person reading the owner's message changes nothing
  sock.ev.emit("chats.update", [{ id: SANJANA, unreadCount: 1 }]);
  sock.ev.emit("messages.update", [{ key: { remoteJid: SANJANA, id: "y", fromMe: true }, update: { status: 4 } }]);
  assert.strictEqual(c.chatIndex.chats.get(SANJANA).unread, 1);
  // the owner replying in the chat from the phone
  await sock.ev.emit("messages.upsert", { type: "notify", messages: [msg("o1", SANJANA, "coming", { fromMe: true })] });
  await tick();
  assert.strictEqual(c.chatIndex.chats.get(SANJANA).unread, 0);
  // group read on the phone: the owner's own read receipt
  sock.ev.emit("chats.update", [{ id: GROUP, unreadCount: 4 }]);
  sock.ev.emit("message-receipt.update", [{ key: { remoteJid: GROUP, id: "g" }, receipt: { userJid: ME, readTimestamp: now() } }]);
  assert.strictEqual(c.chatIndex.chats.get(GROUP).unread, 0);
  // marked unread by hand
  sock.ev.emit("chats.update", [{ id: GROUP, unreadCount: -1 }]);
  assert.strictEqual(c.chatIndex.chats.get(GROUP).unread, 1);
});

test("messages delivered on reconnect are no longer dropped; old ones are flagged history", async () => {
  const { sock, seen } = client();
  sock.ev.emit("messages.upsert", {
    type: "append",
    messages: [msg("off1", ASHOK, "sent while you were offline", { ts: now() - 3600 }), msg("off2", ASHOK, "just now", { ts: now() - 5 })]
  });
  await tick();
  const byId = Object.fromEntries(seen.map((m) => [m.message_id, m]));
  assert.strictEqual(byId.off1.history, true);
  assert.strictEqual(byId.off2.history, undefined);
});

test("chat state changes reach JARVIS and survive a bridge restart", async () => {
  const { c, sock, states, dir } = client();
  sock.ev.emit("chats.update", [{ id: ASHOK, unreadCount: 1 }]);
  await tick();
  assert.ok(states.some((s) => s.chats.some((x) => x.chat_id === ASHOK && x.unread === 1)));
  const again = new ChatIndex(path.join(dir, "chat_index.json"));
  assert.strictEqual(again.chats.get(ASHOK).unread, 1);
  assert.strictEqual(again.synced, false); // saved badges are provisional until this session syncs
  assert.notStrictEqual(again.snapshot().generation, c.getChats().generation);
  c.chatIndex.reset();
  assert.strictEqual(c.getChats().chats.length, 0);
});
