const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { makeOfflineNodeProcessor } = require(path.join(
  path.dirname(require.resolve("@whiskeysockets/baileys")), "Utils/offline-node-processor.js"));

test("a rejected offline message does not stall later queued messages", async () => {
  const handled = [];
  const errors = [];
  const queue = makeOfflineNodeProcessor(new Map([["message", async node => {
    if (node.id === "bad") throw new Error("invalid test node");
    handled.push(node.id);
  }]]), { isWsOpen: () => true, onUnexpectedError: error => errors.push(error.message),
    yieldToEventLoop: () => Promise.resolve() });
  queue.enqueue("message", { id: "bad" });
  queue.enqueue("message", { id: "next" });
  await new Promise(resolve => setImmediate(resolve));
  queue.enqueue("message", { id: "later" });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(handled, ["next", "later"]);
  assert.deepEqual(errors, ["invalid test node"]);
});
