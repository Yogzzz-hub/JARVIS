/**
 * Bounded Reconnection and State Machine for WhatsApp Transport Bridge.
 * Enforces exponential backoff and prevents infinite rapid loops.
 */

const ConnectionState = {
  DISCONNECTED: "DISCONNECTED",
  PAIRING_REQUIRED: "PAIRING_REQUIRED",
  CONNECTING: "CONNECTING",
  CONNECTED: "CONNECTED",
  DEGRADED: "DEGRADED",
  LOGGED_OUT: "LOGGED_OUT"
};

class ReconnectManager {
  constructor({ maxAttempts = 10, baseDelayMs = 1500, maxDelayMs = 30000, onStateChange = null }) {
    this.maxAttempts = maxAttempts;
    this.baseDelayMs = baseDelayMs;
    this.maxDelayMs = maxDelayMs;
    this.onStateChange = onStateChange;

    this.attempts = 0;
    this.currentState = ConnectionState.DISCONNECTED;
    this.timer = null;
  }

  getState() {
    return this.currentState;
  }

  setState(newState, reason = "") {
    if (this.currentState !== newState) {
      this.currentState = newState;
      if (this.onStateChange) {
        this.onStateChange(newState, { reason, attempts: this.attempts });
      }
    }
  }

  onConnected() {
    this.attempts = 0;
    this.clearTimer();
    this.setState(ConnectionState.CONNECTED);
  }

  onDisconnect(canReconnect = true, reason = "") {
    this.clearTimer();
    if (!canReconnect) {
      this.setState(ConnectionState.LOGGED_OUT, reason);
      return false;
    }

    if (this.attempts >= this.maxAttempts) {
      this.setState(ConnectionState.DEGRADED, `Max reconnect attempts (${this.maxAttempts}) reached: ${reason}`);
      return false;
    }

    this.attempts++;
    // Exponential backoff with jitter
    const delay = Math.min(
      this.maxDelayMs,
      this.baseDelayMs * Math.pow(1.5, this.attempts - 1) + Math.random() * 500
    );

    this.setState(ConnectionState.DISCONNECTED, `Reconnecting in ${Math.round(delay)}ms (attempt ${this.attempts}/${this.maxAttempts})`);

    return delay;
  }

  clearTimer() {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  reset() {
    this.clearTimer();
    this.attempts = 0;
    this.setState(ConnectionState.DISCONNECTED);
  }
}

module.exports = {
  ConnectionState,
  ReconnectManager
};
