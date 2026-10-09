"use strict";

/** One exact read-only exception for a controlled, explicitly authorised test. */
function createOneShotGate({ to = "", text = "", requestId = "" } = {}) {
  let consumed = false;
  return {
    consume({ commandOnly = false, id = "", action = "", payload = {} } = {}) {
      if (consumed || !commandOnly || !to || !text || !requestId ||
          action !== "send_text" || id !== requestId ||
          payload?.to !== to || payload?.text !== text || payload?.quoted) return false;
      consumed = true; // claim before entering the network send; uncertain outcomes never retry
      return true;
    },
    get consumed() { return consumed; }
  };
}

module.exports = { createOneShotGate };
