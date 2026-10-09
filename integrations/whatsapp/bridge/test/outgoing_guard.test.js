const test = require("node:test");
const assert = require("node:assert/strict");
const { createOneShotGate } = require("../src/outgoing_guard");

test("one exact authorised text is claimed once before sending", () => {
  const gate = createOneShotGate({ to: "123@lid", text: "JARVIS outgoing acceptance 1004", requestId: "req-1" });
  const command = { commandOnly: true, id: "req-1", action: "send_text",
    payload: { to: "123@lid", text: "JARVIS outgoing acceptance 1004" } };
  assert.equal(gate.consume({ ...command, commandOnly: false }), false);
  assert.equal(gate.consume({ ...command, id: "wrong" }), false);
  assert.equal(gate.consume({ ...command, payload: { ...command.payload, text: "other" } }), false);
  assert.equal(gate.consume({ ...command, action: "send_media" }), false);
  assert.equal(gate.consume({ ...command, payload: { ...command.payload, quoted: { id: "x" } } }), false);
  assert.equal(gate.consumed, false);
  assert.equal(gate.consume(command), true);
  assert.equal(gate.consumed, true);
  assert.equal(gate.consume(command), false); // also after a timeout or uncertain send
});

test("unconfigured read-only gate never allows sending", () => {
  const gate = createOneShotGate();
  assert.equal(gate.consume({ commandOnly: true, id: "req-1", action: "send_text",
    payload: { to: "123@lid", text: "hello" } }), false);
});
