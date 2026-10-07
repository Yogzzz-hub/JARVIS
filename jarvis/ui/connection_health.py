"""Transport health independent from optional integration status."""
from time import monotonic


class ConnectionHealth:
    def __init__(self, grace=10, clock=monotonic):
        self.clock = clock
        self.grace = grace
        self.socket_connected = False
        self.last_ping = self.last_pong = self.last_event = None
        self.backend_health = False
        self.reconnect_attempts = 0
        self.disconnect_reason = None
        self.failed_since = None

    def connected(self):
        self.socket_connected = self.backend_health = True
        self.failed_since = None
        self.disconnect_reason = None
        return 'ONLINE'

    def disconnected(self, reason, healthy):
        self.socket_connected = False
        self.backend_health = healthy
        self.reconnect_attempts += 1
        self.disconnect_reason = str(reason)
        if healthy:
            self.failed_since = None
            return 'RECONNECTING'
        if self.failed_since is None: self.failed_since = self.clock()
        return 'OFFLINE' if self.clock()-self.failed_since >= self.grace else 'RECONNECTING'

    def snapshot(self):
        return {k: v for k, v in vars(self).items() if k != 'clock'}
