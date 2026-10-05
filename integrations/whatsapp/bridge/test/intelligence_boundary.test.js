const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { Readable } = require("node:stream");
const { normalizeIncomingMessage, normalizePendingMessage, isGroupJid } = require("../src/protocol");
const { BaileysClient } = require("../src/baileys_client");
const { saveMediaBuffer } = require("../src/media");
const jid = "919000000001@s.whatsapp.net";

function client(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "jarvis-wa-boundary-"));
  const bridge = new BaileysClient({ authDir: directory, tempDir: path.join(directory, "media") });
  t.after(async () => {
    await bridge.flushMessageCache();
    assert.equal(path.dirname(path.resolve(directory)), path.resolve(os.tmpdir()));
    fs.rmSync(directory, { recursive: true, force: true, maxRetries: 5, retryDelay: 50 });
  });
  return bridge;
}

test("missing transport identity cannot manufacture a MessageRef", () => {
  assert.equal(normalizeIncomingMessage({ key: { remoteJid: jid }, message: { conversation: "hi" } }), null);
});

test("broadcast, status and newsletter traffic cannot masquerade as direct or group chat", () => {
  for (const remoteJid of ["status@broadcast", "123@broadcast", "123@newsletter"]) {
    const raw = { key: { id: "m1", remoteJid }, message: { conversation: "hello" } };
    const decisions = [];
    assert.equal(isGroupJid(remoteJid), false);
    assert.equal(normalizeIncomingMessage(raw, null, d => decisions.push(d)), null);
    assert.equal(decisions[0].reason, "NON_CHAT_CHANNEL");
    assert.equal(normalizePendingMessage(raw), null);
  }
});

test("ephemeral context is preserved and view-once is not unwrapped", () => {
  const raw = { key: { id: "m1", remoteJid: jid }, messageTimestamp: 1700000000,
    message: { ephemeralMessage: { message: { extendedTextMessage: { text: "hello", contextInfo: { stanzaId: "old" } } } } } };
  assert.equal(normalizeIncomingMessage(raw).reply_to.message_id, "old");
  raw.message = { viewOnceMessage: { message: { imageMessage: { caption: "private" } } } };
  assert.equal(normalizeIncomingMessage(raw), null);
});

test("attachment metadata is present before any download", () => {
  const result = normalizeIncomingMessage({ key: { id: "m1", remoteJid: jid },
    message: { documentMessage: { fileName: "report.pdf", mimetype: "application/pdf", fileLength: 400 } } });
  assert.equal(result.media_ref.filename, "report.pdf");
  assert.equal(result.media_ref.downloaded, false);
});

test("on-demand media is strictly scoped to the selected thread", async t => {
  const bridge = client(t);
  bridge.rememberNormalized({ message_id: "m1", chat_id: jid, media_ref: { mimetype: "text/plain" } });
  let downloads = 0;
  bridge.downloadMediaMessage = async () => { downloads += 1; return Readable.from([Buffer.from("real file")]); };
  bridge.sock = {};
  bridge.saveMessage("m1", { documentMessage: {} });
  assert.equal(await bridge.getMessageWithMedia("m1", "other@lid", true), null);
  assert.equal(downloads, 0);
  const result = await bridge.getMessageWithMedia("m1", jid, true);
  assert.equal(fs.readFileSync(result.media_ref.file_path, "utf8"), "real file");
  assert.equal(downloads, 1);
  await bridge.getMessageWithMedia("m1", jid, true);
  assert.equal(downloads, 1);
});

test("a lying attachment length still has a streaming byte limit", async t => {
  const bridge = client(t);
  bridge.rememberNormalized({ message_id: "m1", chat_id: jid, media_ref: { mimetype: "text/plain", size_bytes: 1 } });
  bridge.saveMessage("m1", { documentMessage: {} });
  bridge.sock = {};
  bridge.downloadMediaMessage = async () => Readable.from([Buffer.alloc(25 * 1024 * 1024), Buffer.alloc(1)]);
  await assert.rejects(bridge.getMessageWithMedia("m1", jid, true), /25 MB/);
  assert.equal(fs.existsSync(bridge.tempDir), false);
});

test("oversized media is rejected before a cache file is written", async t => {
  const bridge = client(t);
  await assert.rejects(saveMediaBuffer(Buffer.alloc(25 * 1024 * 1024 + 1), "text/plain", "file", bridge.tempDir), /25 MB/);
  assert.deepEqual(fs.readdirSync(bridge.tempDir), []);
});
