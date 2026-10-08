import json
import tempfile
import time
import unittest
from pathlib import Path

from mind_the_limit import config, device, panel, protocol, runner, usage
from mind_the_limit.usage import Meter
from tests.fakes import FakeLink


class FakeClock:
    def __init__(self, hour=12):
        self.hour = hour
        self.slept = []
        self.now = 1_000_000.0

    def time(self):
        return self.now

    def strftime(self, fmt):
        return time.strftime(fmt, time.struct_time((2026, 10, 7, self.hour, 0, 0, 2, 280, -1)))

    def localtime(self):
        return time.struct_time((2026, 10, 7, self.hour, 0, 0, 2, 280, -1))

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class Source:
    def __init__(self, *results):
        self.results = list(results)

    def __call__(self, claude=None):
        result = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(result, Exception):
            raise result
        return result


METERS = [Meter("session", "session", 15), Meter("week", "all models", 34), Meter("model", "Fable", 0)]


def images(link):
    return [d for d in link.sent if d[3] == protocol.IMAGE]


class RunnerTest(unittest.TestCase):
    def make(self, source, link=None, state=None, hour=12, **cfg):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.link = link or FakeLink()
        self.lines = []
        settings = dict(config.DEFAULTS, device="11-22-33-44-55-66", **cfg)
        return runner.Runner(settings, device.Timebox(self.link), "en", read_usage=source,
                             read_state=lambda: state, clock=FakeClock(hour), log=self.lines.append,
                             state_file=Path(self.tmp.name) / "state.json")

    def test_reading_is_drawn_and_sent(self):
        r = self.make(Source(METERS))
        r.poll()
        self.assertEqual(images(self.link), [protocol.image(panel.render(METERS))])
        self.assertIn(protocol.quiet()[:9], b"".join(self.link.sent))
        self.assertTrue(any("Session 15% | week 34% | Fable 0%" in line for line in self.lines), self.lines)

    def test_a_new_value_replaces_the_picture(self):
        changed = [Meter("session", "session", 16)] + METERS[1:]
        r = self.make(Source(METERS, changed))
        r.poll()
        r.poll()
        self.assertEqual(images(self.link)[-1], protocol.image(panel.render(changed)))

    def test_one_failed_reading_keeps_the_last_picture_and_retries_soon(self):
        r = self.make(Source(METERS, usage.UsageUnavailable("claude-failed")))
        r.poll()
        r.clock.now += 300
        r.poll()
        self.assertEqual(images(self.link)[-1], protocol.image(panel.render(METERS)))
        self.assertTrue(r.retry_soon)
        self.assertIn("kept", self.lines[-1])

    def test_cycle_after_a_failed_reading_waits_only_a_minute(self):
        r = self.make(Source(METERS, usage.UsageUnavailable("claude-failed"), METERS))
        r.cycle()
        r.clock.slept.clear()
        r.cycle()
        self.assertEqual(r.clock.slept, [runner.RETRY_AFTER_FAILURE])

    def test_values_older_than_the_limit_give_way_to_the_error(self):
        r = self.make(Source(METERS, usage.UsageUnavailable("claude-failed")))
        r.poll()
        r.clock.now += runner.STALE_AFTER + 1
        r.poll()
        self.assertEqual(images(self.link)[-1], protocol.image(panel.render_error("usage")))

    def test_unreadable_limits_show_the_error_not_old_numbers(self):
        r = self.make(Source(usage.UsageUnavailable("no-limits")))
        r.poll()
        self.assertEqual(images(self.link)[-1], protocol.image(panel.render_error("usage")))
        state = json.loads((Path(self.tmp.name) / "state.json").read_text())
        self.assertEqual(state["meters"], [])
        self.assertIn("no-limits", state["error"])

    def test_missing_claude_has_its_own_symbol(self):
        r = self.make(Source(usage.UsageUnavailable("claude-missing")))
        r.poll()
        self.assertEqual(images(self.link)[-1], protocol.image(panel.render_error("claude")))

    def test_same_problem_is_logged_once(self):
        r = self.make(Source(usage.UsageUnavailable("no-limits")))
        r.poll()
        r.poll()
        self.assertEqual(sum("not readable" in line for line in self.lines), 1)

    def test_dark_entity_turns_the_box_off(self):
        r = self.make(Source(METERS), state="off", ha_entity="binary_sensor.lights")
        r.adjust_brightness()
        self.assertEqual(self.link.sent[-1], protocol.brightness(0))
        self.assertIn("binary_sensor.lights is off", self.lines[-1])

    def test_unreachable_home_assistant_keeps_the_time_value(self):
        r = self.make(Source(METERS), state=None, hour=23)
        r.adjust_brightness()
        self.assertEqual(self.link.sent[-1], protocol.brightness(10))

    def test_brightness_is_sent_only_when_it_changes(self):
        r = self.make(Source(METERS))
        r.adjust_brightness()
        sent = len(self.link.sent)
        r.adjust_brightness()
        self.assertEqual(len(self.link.sent), sent)

    def test_unreachable_box_waits_and_does_not_crash(self):
        r = self.make(Source(METERS), link=FakeLink(open_results=[-1] * 10))
        r.cycle()
        self.assertEqual(r.clock.slept, [runner.RETRY_SECONDS])
        self.assertIn("not reachable", self.lines[-1])
        self.assertFalse(r.connected)

    def test_cycle_waits_the_interval_in_one_minute_steps(self):
        r = self.make(Source(METERS), interval=300)
        r.cycle()
        self.assertEqual(r.clock.slept, [60, 60, 60, 60, 60])
        pings = [d for d in self.link.sent if d == protocol.state_request()]
        self.assertEqual(len(pings), 1 + 4)   # one to verify the connection, then one per minute but the last


if __name__ == "__main__":
    unittest.main()
