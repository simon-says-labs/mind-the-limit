import contextlib
import io
import json
import os
import plistlib
import string
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from mind_the_limit import __main__ as cli
from mind_the_limit import agent, config, homeassistant, texts


class Isolated(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = {"MIND_THE_LIMIT_HOME": str(self.root / "app"), "MIND_THE_LIMIT_LOG": str(self.root / "m.log"),
               "MIND_THE_LIMIT_PLIST": str(self.root / "agent.plist")}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["--language", "en"] + list(argv))
        return code, out.getvalue()


class TextsTest(unittest.TestCase):
    def test_every_language_has_every_key_with_the_same_placeholders(self):
        def fields(text):
            return sorted(f for _, f, _, _ in string.Formatter().parse(text) if f)
        for lang in texts.LANGUAGES:
            self.assertEqual(set(texts.TEXTS[lang]), set(texts.TEXTS["en"]), lang)
            for key, text in texts.TEXTS["en"].items():
                self.assertEqual(fields(texts.TEXTS[lang][key]), fields(text), (lang, key))

    def test_detect_from_environment_and_macos(self):
        self.assertEqual(texts.detect(env={"LANG": "de_DE.UTF-8"}), "de")
        fake = lambda *a, **k: subprocess.CompletedProcess(a, 0, '(\n    "it-IT",\n    "en-US"\n)\n', "")
        self.assertEqual(texts.detect(run=fake, env={}), "it")


class SetAndPreviewTest(Isolated):
    def test_set_validates_and_saves(self):
        self.assertEqual(self.run_cli("set", "device", "aa:bb:cc:dd:ee:ff")[0], 0)
        self.assertEqual(config.load()["device"], "AA-BB-CC-DD-EE-FF")
        code, out = self.run_cli("set", "interval", "10")
        self.assertEqual(code, 2)
        self.assertIn("Not a valid value", out)

    def test_preview_from_values_and_errors(self):
        for extra in (["--values", "15,34,0"], ["--error", "usage"], ["--error", "claude"]):
            out_file = self.root / ("p%d.png" % len(extra[1]))
            code, out = self.run_cli("preview", "--out", str(out_file), *extra)
            self.assertEqual(code, 0)
            self.assertEqual(out_file.read_bytes()[:4], b"\x89PNG")

    def test_status_without_anything(self):
        code, out = self.run_cli("status")
        self.assertEqual(code, 0)
        self.assertIn("No reading yet", out)

    def test_status_shows_last_reading_and_problem(self):
        config.state_path().parent.mkdir(parents=True)
        config.state_path().write_text(json.dumps({"time": "t1", "meters": [{"label": "session", "percent": 15}],
                                                   "error_time": "t2", "error": "no-limits"}))
        out = self.run_cli("status")[1]
        self.assertIn("Last reading t1: session 15%", out)
        self.assertIn("Last problem t2: no-limits", out)

    def test_run_without_device_explains_what_to_do(self):
        code, out = self.run_cli("run", "--once")
        self.assertEqual(code, 2)
        self.assertIn("mind-the-limit find", out)


class AgentTest(Isolated):
    def test_plist_runs_the_venv_python_and_finds_claude(self):
        plist = agent.agent_plist(Path("/A"), Path("/L/m.log"), "/x/bin/claude")
        self.assertEqual(plist["ProgramArguments"], ["/A/venv/bin/python", "-m", "mind_the_limit", "run"])
        self.assertEqual(plist["EnvironmentVariables"]["PYTHONPATH"], "/A/app")
        self.assertTrue(plist["EnvironmentVariables"]["PATH"].startswith("/x/bin:"))
        self.assertTrue(plist["KeepAlive"])
        self.assertNotIn("WorkingDirectory", plist)
        plistlib.dumps(plist)

    def test_install_without_agent(self):
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            if cmd[1:3] == ["-m", "venv"]:
                (Path(cmd[3]) / "bin").mkdir(parents=True)
                (Path(cmd[3]) / "bin" / "python").write_text("")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        source = Path(cli.__file__).resolve().parent
        self.assertEqual(agent.install(source, "/py", with_agent=False, run=run, home=self.root), 0)
        app = config.home()
        self.assertTrue((app / "app" / "mind_the_limit" / "runner.py").exists())
        self.assertIn(agent.PYOBJC, calls[1])
        self.assertTrue(os.access(app / "mind-the-limit", os.X_OK))
        # a second install moves the old program to the Trash instead of deleting it
        self.assertEqual(agent.install(source, "/py", with_agent=False, run=run, home=self.root), 0)
        self.assertEqual(len(list((self.root / ".Trash").glob("mind-the-limit-old-program-*"))), 1)

    def test_python_must_be_recent(self):
        old = lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, "False\n", "")
        new = lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, "True\n", "")
        self.assertIsNone(agent.find_python("/usr/bin/python3", run=old))
        self.assertEqual(agent.find_python("/p/python3.12", run=new), "/p/python3.12")

    def test_uninstall_moves_to_the_trash(self):
        config.home().mkdir(parents=True)
        (config.home() / "config.json").write_text("{}")
        with mock.patch.object(agent, "launchctl", return_value=0):
            trash = agent.uninstall(home=self.root)
        self.assertFalse(config.home().exists())
        self.assertTrue((trash / "app" / "config.json").exists())


class FakeHA:
    """Answers like Home Assistant: /api/ needs the token, /api/states/<entity> knows one entity."""

    def __init__(self, token="good", entity="binary_sensor.lights"):
        self.token, self.entity = token, entity

    def __call__(self, request, timeout):
        auth = request.get_header("Authorization") or ""
        if not auth:
            raise urllib.error.HTTPError(request.full_url, 401, "", {}, io.BytesIO(b""))
        if auth != "Bearer " + self.token:
            raise urllib.error.HTTPError(request.full_url, 401, "", {}, io.BytesIO(b""))
        if request.full_url.endswith("/api/"):
            return Response(b'{"message": "API running."}')
        if request.full_url.endswith("/api/states/" + self.entity):
            return Response(b'{"state": "on"}')
        raise urllib.error.HTTPError(request.full_url, 404, "", {}, io.BytesIO(b""))


class Response(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class ConnectHATest(Isolated):
    def connect(self, **kw):
        stored, lines = [], []
        code = homeassistant.connect("en", opener=FakeHA(), store=stored.append, say=lines.append,
                                     browser=lambda url: lines.append("BROWSER " + url), **kw)
        return code, stored, lines

    def test_interactive(self):
        answers = iter(["http://ha:8123", "binary_sensor.lights"])
        code, stored, lines = self.connect(ask=lambda prompt: next(answers), ask_secret=lambda prompt: "good")
        self.assertEqual(code, 0)
        self.assertEqual(stored, ["good"])
        self.assertIn("BROWSER http://ha:8123/profile/security", lines)
        self.assertEqual(config.load()["ha_entity"], "binary_sensor.lights")
        self.assertTrue(all("good" not in line for line in lines))

    def test_wrong_token_is_not_stored(self):
        answers = iter(["http://ha:8123", "binary_sensor.lights"])
        code, stored, lines = self.connect(ask=lambda prompt: next(answers), ask_secret=lambda prompt: "bad")
        self.assertEqual((code, stored), (1, []))
        self.assertIn("did not accept", lines[-1])

    def test_unknown_entity_is_not_stored(self):
        answers = iter(["http://ha:8123", "light.nope"])
        code, stored, _ = self.connect(ask=lambda prompt: next(answers), ask_secret=lambda prompt: "good")
        self.assertEqual((code, stored), (1, []))

    def test_from_environment(self):
        with mock.patch.dict(os.environ, {"U": "http://ha:8123", "T": "good"}):
            code, stored, _ = self.connect(from_env=("U", "T"), entity="binary_sensor.lights")
        self.assertEqual((code, stored), (0, ["good"]))

    def test_from_environment_missing_variable(self):
        with mock.patch.dict(os.environ, {"U": "http://ha:8123"}, clear=False):
            os.environ.pop("T", None)
            code, stored, lines = self.connect(from_env=("U", "T"), entity="binary_sensor.lights")
        self.assertEqual((code, stored), (2, []))
        self.assertIn("T is empty", lines[-1])


if __name__ == "__main__":
    unittest.main()
