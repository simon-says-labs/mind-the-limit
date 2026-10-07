import io
import json
import os
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from mind_the_limit import brightness, config, keychain

CFG = dict(config.DEFAULTS)


class NightWindowTest(unittest.TestCase):
    def test_window_across_midnight(self):
        self.assertFalse(brightness.is_night(22, 23, 7))
        self.assertTrue(brightness.is_night(23, 23, 7))
        self.assertTrue(brightness.is_night(6, 23, 7))
        self.assertFalse(brightness.is_night(7, 23, 7))

    def test_window_within_a_day(self):
        self.assertTrue(brightness.is_night(13, 12, 14))
        self.assertFalse(brightness.is_night(14, 12, 14))

    def test_empty_window(self):
        self.assertFalse(brightness.is_night(3, 5, 5))


class TargetTest(unittest.TestCase):
    def test_day_and_night(self):
        self.assertEqual(brightness.target(22, CFG, None), 60)
        self.assertEqual(brightness.target(23, CFG, None), 10)

    def test_dark_entity_turns_the_panel_off(self):
        self.assertEqual(brightness.target(12, CFG, True), 0)

    def test_light_entity_keeps_the_time_value(self):
        self.assertEqual(brightness.target(0, CFG, False), 10)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class EntityTest(unittest.TestCase):
    def opener(self, state=None, error=None):
        seen = []

        def open_(request, timeout):
            seen.append(request)
            if error:
                raise error
            return FakeResponse(json.dumps({"state": state}).encode())
        return open_, seen

    def test_reads_the_state_with_the_token(self):
        open_, seen = self.opener("off")
        self.assertEqual(brightness.entity_state("http://ha:8123/", "tok", "binary_sensor.x", opener=open_), "off")
        self.assertEqual(seen[0].full_url, "http://ha:8123/api/states/binary_sensor.x")
        self.assertEqual(seen[0].get_header("Authorization"), "Bearer tok")

    def test_unreachable_or_unknown_is_none(self):
        for open_ in (self.opener(error=urllib.error.URLError("down"))[0], self.opener("unavailable")[0],
                      self.opener("unknown")[0]):
            self.assertIsNone(brightness.entity_state("http://ha", "tok", "x.y", opener=open_))

    def test_not_configured_is_none_without_a_request(self):
        open_, seen = self.opener("off")
        self.assertIsNone(brightness.entity_state("", "tok", "x.y", opener=open_))
        self.assertEqual(seen, [])

    def test_dark_states(self):
        self.assertTrue(brightness.is_dark("off", ["off", "not_home"]))
        self.assertTrue(brightness.is_dark("not_home", ["off", "not_home"]))
        self.assertFalse(brightness.is_dark("on", ["off"]))
        self.assertIsNone(brightness.is_dark(None, ["off"]))


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "config.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_defaults_when_missing_or_broken(self):
        self.assertEqual(config.load(self.path), config.DEFAULTS)
        self.path.write_text("{broken")
        self.assertEqual(config.load(self.path), config.DEFAULTS)

    def test_round_trip_ignores_unknown_keys(self):
        cfg = config.set_value(config.load(self.path), "device", "11:22:33:aa:bb:cc")
        cfg["junk"] = 1
        config.save(cfg, self.path)
        loaded = config.load(self.path)
        self.assertEqual(loaded["device"], "11-22-33-AA-BB-CC")
        self.assertNotIn("junk", loaded)

    def test_validation(self):
        for key, raw in (("device", "nope"), ("interval", "30"), ("night_start", "24"), ("bright_day", "101"),
                         ("colors.session", "red"), ("colors.banana", "#FFFFFF"), ("unknown", "1")):
            with self.assertRaises(ValueError, msg=key):
                config.parse_value(key, raw)

    def test_colours(self):
        cfg = config.set_value(CFG, "colors.week", "00ff00")
        self.assertEqual(config.colors(cfg), {"week": 0x00FF00})

    def test_paths_follow_the_environment(self):
        with mock.patch.dict(os.environ, {"MIND_THE_LIMIT_HOME": "/x/y", "MIND_THE_LIMIT_LOG": "/x/l.log"}):
            self.assertEqual(config.config_path(), Path("/x/y/config.json"))
            self.assertEqual(config.log_path(), Path("/x/l.log"))


class KeychainTest(unittest.TestCase):
    def fake_security(self):
        store = {}
        calls = []

        def run(cmd, input=None, **kw):
            calls.append((cmd, input))
            if cmd[:2] == ["security", "-i"]:
                parts = input.split()
                store["token"] = parts[parts.index("-w") + 1]
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if cmd[1] == "find-generic-password":
                return subprocess.CompletedProcess(cmd, 0 if "token" in store else 44, store.get("token", "") + "\n", "")
            if cmd[1] == "delete-generic-password":
                return subprocess.CompletedProcess(cmd, 0 if store.pop("token", None) else 44, "", "")
            raise AssertionError(cmd)
        return run, calls

    def test_token_goes_through_stdin_not_arguments(self):
        run, calls = self.fake_security()
        keychain.store_token("abc.def-ghi_jkl", run=run)
        self.assertEqual(keychain.read_token(run=run), "abc.def-ghi_jkl")
        self.assertTrue(all("abc.def" not in " ".join(cmd) for cmd, _ in calls))

    def test_unsafe_token_is_refused(self):
        run, calls = self.fake_security()
        with self.assertRaises(keychain.KeychainError):
            keychain.store_token("abc def; rm", run=run)
        self.assertEqual(calls, [], "an unsafe token must never reach the security command")

    def test_forget(self):
        run, _ = self.fake_security()
        keychain.store_token("t", run=run)
        self.assertTrue(keychain.forget_token(run=run))
        self.assertEqual(keychain.read_token(run=run), "")
        self.assertFalse(keychain.forget_token(run=run))


if __name__ == "__main__":
    unittest.main()
