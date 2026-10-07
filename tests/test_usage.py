import json
import subprocess
import unittest
from pathlib import Path

from mind_the_limit import usage

FIXTURES = Path(__file__).parent / "fixtures"
REAL = (FIXTURES / "usage-subscription.jsonl").read_text(encoding="utf-8")


def events(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def stream(*evs):
    return "\n".join(json.dumps(e) for e in evs) + "\n"


def text_only(text):
    return stream({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})


class StructuredReportTest(unittest.TestCase):
    def test_real_output_gives_three_meters_in_order(self):
        meters = usage.parse_stream(REAL)
        self.assertEqual([(m.kind, m.percent) for m in meters], [("session", 15), ("week", 34), ("model", 0)])
        self.assertEqual(meters[2].label, "Fable")
        self.assertEqual(meters[0].resets_at, "2026-10-08T00:40:00.936393+00:00")

    def test_structured_report_wins_over_text(self):
        evs = events(REAL)
        evs[1]["message"]["content"][0]["text"] = "Current session: 99% used"
        meters = usage.parse_stream(stream(*evs))
        self.assertEqual(meters[0].percent, 15)

    def test_unknown_kind_is_kept_after_the_known_ones(self):
        evs = events(REAL)
        limits = evs[1]["usage_report"]["rate_limits"]["limits"]
        limits.insert(0, {"kind": "monthly_something", "group": "monthly", "percent": 7, "scope": None})
        meters = usage.parse_stream(stream(*evs))
        self.assertEqual([m.kind for m in meters], ["session", "week", "model", "other"])

    def test_fractions_and_values_above_100_are_kept_as_numbers(self):
        evs = events(REAL)
        evs[1]["usage_report"]["rate_limits"]["limits"][0]["percent"] = 104.6
        self.assertEqual(usage.parse_stream(stream(*evs))[0].percent, 104.6)


class TextFallbackTest(unittest.TestCase):
    def test_text_without_structured_report(self):
        meters = usage.parse_text(
            "Current session: 15% used · resets Oct 8 at 2:40am (Europe/Berlin)\n"
            "Current week (all models): 34% used · resets Oct 12 at 10pm (Europe/Berlin)\n"
            "Current week (Fable): 0% used · resets Oct 12 at 10pm (Europe/Berlin)\n")
        self.assertEqual([(m.kind, m.label, m.percent) for m in meters],
                         [("session", "session", 15), ("week", "all models", 34), ("model", "Fable", 0)])

    def test_without_model_line(self):
        meters = usage.parse_stream(text_only("Current session: 3% used\nCurrent week (all models): 4% used"))
        self.assertEqual(len(meters), 2)

    def test_extra_model_line(self):
        meters = usage.parse_stream(text_only(
            "Current session: 3% used\nCurrent week (all models): 4% used\n"
            "Current week (Fable): 5% used\nCurrent week (Opus): 6% used"))
        self.assertEqual([m.label for m in meters], ["session", "all models", "Fable", "Opus"])

    def test_full_limit(self):
        self.assertEqual(usage.parse_text("Current session: 100% used")[0].percent, 100)

    def test_no_subscription_text_raises(self):
        with self.assertRaises(usage.UsageUnavailable) as ctx:
            usage.parse_stream(text_only("You are using an API key. Usage limits do not apply."))
        self.assertEqual(ctx.exception.reason, "no-limits")

    def test_garbage_lines_are_skipped(self):
        meters = usage.parse_stream("not json\n" + REAL + "{broken\n")
        self.assertEqual(len(meters), 3)


class ReadUsageTest(unittest.TestCase):
    def test_runs_claude_with_stream_json_and_parses(self):
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, REAL, "")

        meters = usage.read_usage(claude="/x/claude", run=run)
        self.assertEqual(len(meters), 3)
        self.assertEqual(calls[0], ["/x/claude", "-p", "/usage", "--output-format", "stream-json", "--verbose"])

    def test_missing_claude(self):
        with self.assertRaises(usage.UsageUnavailable) as ctx:
            usage.read_usage(claude=None, which=lambda name, path=None: None)
        self.assertEqual(ctx.exception.reason, "claude-missing")

    def test_claude_fails(self):
        def run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 1, "", "Not logged in")
        with self.assertRaises(usage.UsageUnavailable) as ctx:
            usage.read_usage(claude="/x/claude", run=run)
        self.assertEqual(ctx.exception.reason, "claude-failed")
        self.assertIn("Not logged in", ctx.exception.detail)

    def test_timeout(self):
        def run(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
        with self.assertRaises(usage.UsageUnavailable) as ctx:
            usage.read_usage(claude="/x/claude", run=run)
        self.assertEqual(ctx.exception.reason, "claude-failed")


if __name__ == "__main__":
    unittest.main()
