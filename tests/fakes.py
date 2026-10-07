"""Stand-ins for the Bluetooth link, so the device logic and the runner can be tested anywhere."""
from mind_the_limit import protocol

REPLY = bytes([0x01, 0x10, 0x00, 0x04, 0x46, 0x55, 0x80, 0x02])


class FakeLink:
    """Behaves like MacLink. `open_results` are returned by successive open() calls (0 = success);
    `answers` says whether the box replies to a state request; `write_results` overrides writes."""

    def __init__(self, open_results=(0,), answers=True, write_results=()):
        self.open_results = list(open_results)
        self.answers = answers
        self.write_results = list(write_results)
        self.opened = False
        self.received = bytearray()
        self.sent = []
        self.events = []
        self.waited = 0.0

    def open(self):
        result = self.open_results.pop(0) if self.open_results else 0
        self.events.append("open:%s" % result)
        self.opened = result == 0
        return result

    def is_open(self):
        return self.opened

    def write(self, data):
        result = self.write_results.pop(0) if self.write_results else 0
        if result != 0:
            self.opened = False
            return result
        self.sent.append(bytes(data))
        if data == protocol.state_request() and self.answers:
            self.received += REPLY
        return 0

    def peek_received(self):
        return bytes(self.received)

    def take_received(self):
        data = bytes(self.received)
        self.received.clear()
        return data

    def wait(self, seconds):
        self.waited += seconds

    def close(self):
        if self.opened:
            self.events.append("close")
        self.opened = False

    def drop_connection(self):
        self.events.append("drop")
