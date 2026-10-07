import unittest

from mind_the_limit import device, protocol
from tests.fakes import FakeLink


class ConnectTest(unittest.TestCase):
    def test_first_open_with_an_answer(self):
        link = FakeLink()
        device.Timebox(link).connect()
        self.assertEqual(link.events, ["open:0"])
        self.assertEqual(link.sent, [protocol.state_request()])

    def test_blocked_channel_drops_the_connection_and_retries(self):
        link = FakeLink(open_results=(-536870212, -536870212, 0))
        device.Timebox(link).connect()
        self.assertEqual(link.events, ["open:-536870212", "drop", "open:-536870212", "drop", "open:0"])

    def test_open_without_an_answer_is_not_a_connection(self):
        link = FakeLink(answers=False)
        with self.assertRaises(device.DeviceError):
            device.Timebox(link).connect()
        self.assertEqual(link.events.count("drop"), device.ATTEMPTS - 1)
        self.assertEqual(link.events.count("close"), device.ATTEMPTS)

    def test_never_more_than_the_attempts(self):
        link = FakeLink(open_results=[-1] * 10)
        with self.assertRaises(device.DeviceError):
            device.Timebox(link).connect()
        self.assertEqual(sum(e.startswith("open") for e in link.events), device.ATTEMPTS)


class SendTest(unittest.TestCase):
    def test_send_connects_when_needed(self):
        link = FakeLink()
        device.Timebox(link).send(protocol.brightness(10))
        self.assertEqual(link.sent, [protocol.state_request(), protocol.brightness(10)])

    def test_failed_write_reconnects_once(self):
        link = FakeLink()
        box = device.Timebox(link)
        box.connect()
        link.write_results = [1]
        box.send(protocol.brightness(10))
        self.assertEqual(link.sent[-1], protocol.brightness(10))
        self.assertEqual(link.events.count("open:0"), 2)

    def test_write_failing_twice_raises(self):
        link = FakeLink()
        box = device.Timebox(link)
        box.connect()
        link.write_results = [1, 0, 1]   # data fails, state request on reconnect works, data fails again
        with self.assertRaises(device.DeviceError):
            box.send(protocol.brightness(10))

    def test_ping(self):
        link = FakeLink()
        box = device.Timebox(link)
        self.assertTrue(box.ping())
        link.answers = False
        self.assertFalse(box.ping())


if __name__ == "__main__":
    unittest.main()
