const test = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { BaileysClient } = require('../src/baileys_client');
const { normalizeIncomingMessage } = require('../src/protocol');

test('normalization reports exact rejection and accepts a wrapped direct message without losing identity', () => {
  const decisions = [];
  const bare = { key: { id: 'trace-1', remoteJid: '123@lid' }, message: { protocolMessage: {} } };
  assert.equal(normalizeIncomingMessage(bare, null, d => decisions.push(d)), null);
  assert.equal(decisions[0].reason, 'UNSUPPORTED_MESSAGE_TYPE');
  const wrapped = { ...bare, messageTimestamp: 123, message: { ephemeralMessage: { message: { conversation: 'private text' } } } };
  const normalized = normalizeIncomingMessage(wrapped, null, d => decisions.push(d));
  assert.equal(normalized.message_id, 'trace-1');
  assert.equal(normalized.chat_id, '123@lid');
  assert.equal(normalized.is_group, false);
  assert.equal(normalized.text, 'private text');
  assert.equal(decisions[1].result, 'ACCEPTED');
});

test('rebind removes the obsolete upsert handler and traces metadata without message text', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wa-incoming-trace-'));
  const file = path.join(dir, 'trace.jsonl');
  const previous = process.env.JARVIS_WHATSAPP_TRACE_NODE;
  process.env.JARVIS_WHATSAPP_TRACE_NODE = file;
  try {
    const seen = [];
    const client = new BaileysClient({ authDir: dir, tempDir: dir, onNormalizedMessage: m => seen.push(m) });
    const oldSock = { ev: new EventEmitter(), user: { id: 'me@s.whatsapp.net' } };
    client.sock = oldSock;
    client.bindEvents(oldSock);
    const newSock = { ev: new EventEmitter(), user: { id: 'me@s.whatsapp.net' } };
    client.sock = newSock;
    client.bindEvents(newSock);
    assert.equal(oldSock.ev.listenerCount('messages.upsert'), 0);
    assert.equal(newSock.ev.listenerCount('messages.upsert'), 1);
    const raw = { key: { id: 'trace-2', remoteJid: '123@lid', fromMe: false },
      message: { conversation: 'never log this private body' }, messageTimestamp: Math.floor(Date.now() / 1000) };
    oldSock.ev.emit('messages.upsert', { messages: [raw], type: 'notify' });
    newSock.ev.emit('messages.upsert', { messages: [raw], type: 'notify' });
    await new Promise(resolve => setTimeout(resolve, 20));
    assert.equal(seen.length, 1);
    const lines = fs.readFileSync(file, 'utf8').trim().split('\n').map(JSON.parse);
    assert.ok(lines.some(x => x.stage === 'upsert_handler' && x.message_id === 'trace-2'));
    assert.ok(lines.some(x => x.stage === 'normalization' && x.normalization_result === 'ACCEPTED'));
    assert.ok(!fs.readFileSync(file, 'utf8').includes('never log this private body'));
  } finally {
    if (previous === undefined) delete process.env.JARVIS_WHATSAPP_TRACE_NODE;
    else process.env.JARVIS_WHATSAPP_TRACE_NODE = previous;
    for (const name of fs.readdirSync(dir)) {
      const target = path.join(dir, name);
      if (fs.statSync(target).isFile()) fs.unlinkSync(target);
    }
    fs.rmdirSync(dir);
  }
});

test('decrypt errors are classified by message ID without logging error text or payload', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wa-decrypt-trace-'));
  const file = path.join(dir, 'trace.jsonl');
  const previous = process.env.JARVIS_WHATSAPP_TRACE_NODE;
  process.env.JARVIS_WHATSAPP_TRACE_NODE = file;
  try {
    const client = new BaileysClient({ authDir: dir, tempDir: dir });
    client._rawNodeMeta = new Map([['decrypt-1', { chat_jid: '123@lid', timestamp: 123 }]]);
    client.logger.error({ key: { id: 'decrypt-1', remoteJid: '123@lid', fromMe: false },
      err: new Error('Bad MAC: private diagnostic details'), messageType: 'msg',
      author: '123@lid' }, 'failed to decrypt message');
    const trace = fs.readFileSync(file, 'utf8');
    const row = JSON.parse(trace.trim());
    assert.equal(row.stage, 'baileys_decrypt_error');
    assert.equal(row.message_id, 'decrypt-1');
    assert.equal(row.reason, 'BAD_MAC');
    assert.equal(row.timestamp, 123);
    assert.ok(!trace.includes('private diagnostic details'));
  } finally {
    if (previous === undefined) delete process.env.JARVIS_WHATSAPP_TRACE_NODE;
    else process.env.JARVIS_WHATSAPP_TRACE_NODE = previous;
    for (const name of fs.readdirSync(dir)) {
      const target = path.join(dir, name);
      if (fs.statSync(target).isFile()) fs.unlinkSync(target);
    }
    fs.rmdirSync(dir);
  }
});
