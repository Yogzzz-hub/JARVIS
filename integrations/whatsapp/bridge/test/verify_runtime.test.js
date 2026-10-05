"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const path = require("node:path");
const { verifyStatus } = require("../scripts/verify_runtime");

const fresh = path.resolve("integrations/data/whatsapp_auth_fresh_latency_test");
const old = path.resolve("integrations/data/whatsapp_auth");

test("normal startup rejects the archived WhatsApp auth even if the socket is connected", () => {
  const status = { state: "CONNECTED", identity: { auth_path: old, auth_registered: true },
    event_health: { received_pending_notifications: true } };
  assert.deepEqual(verifyStatus(status, fresh), { code: 3, reason: "WRONG_AUTH_STORE" });
});

test("normal startup waits for fresh session registration and notification completion", () => {
  const status = { state: "CONNECTED", identity: { auth_path: fresh, auth_registered: true },
    event_health: { received_pending_notifications: false } };
  assert.deepEqual(verifyStatus(status, fresh), { code: 4, reason: "SESSION_NOT_READY" });
  status.event_health.received_pending_notifications = true;
  assert.deepEqual(verifyStatus(status, fresh), { code: 0, reason: "READY" });
});
