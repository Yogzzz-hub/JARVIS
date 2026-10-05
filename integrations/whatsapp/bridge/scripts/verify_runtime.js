"use strict";

// Read-only startup guard. Never treats another process bound to port 8768 as our bridge.
const path = require("path");
const WebSocket = require("ws");

function samePath(left, right) {
  const a = path.resolve(String(left || ""));
  const b = path.resolve(String(right || ""));
  return process.platform === "win32" ? a.toLowerCase() === b.toLowerCase() : a === b;
}

function verifyStatus(payload, expectedAuth) {
  if (!payload?.identity?.auth_path || !samePath(payload.identity.auth_path, expectedAuth)) {
    return { code: 3, reason: "WRONG_AUTH_STORE" };
  }
  if (payload.state !== "CONNECTED" || !payload.identity.auth_registered ||
      payload.event_health?.received_pending_notifications !== true) {
    return { code: 4, reason: "SESSION_NOT_READY" };
  }
  return { code: 0, reason: "READY" };
}

function checkRuntime(expectedAuth, port = 8768) {
  return new Promise((resolve) => {
    let finished = false;
    const finish = (result) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      try { socket.close(); } catch (_) {}
      resolve(result);
    };
    const socket = new WebSocket(`ws://127.0.0.1:${port}/diagnostics`);
    const timer = setTimeout(() => finish({ code: 2, reason: "DIAGNOSTICS_TIMEOUT" }), 3000);
    socket.on("message", (data) => {
      try {
        const event = JSON.parse(data.toString());
        finish(verifyStatus(event.payload, expectedAuth));
      } catch (_) {
        finish({ code: 2, reason: "INVALID_DIAGNOSTICS" });
      }
    });
    socket.on("error", () => finish({ code: 2, reason: "BRIDGE_UNAVAILABLE" }));
    socket.on("close", () => finish({ code: 2, reason: "BRIDGE_CLOSED" }));
  });
}

if (require.main === module) {
  const expectedAuth = process.argv[2];
  if (!expectedAuth) {
    process.stderr.write("EXPECTED_AUTH_PATH_REQUIRED\n");
    process.exitCode = 2;
  } else {
    checkRuntime(expectedAuth).then((result) => {
      process.stdout.write(`${result.reason}\n`);
      process.exitCode = result.code;
    });
  }
}

module.exports = { samePath, verifyStatus, checkRuntime };
