"""Installing, inspecting and removing the program and its background job (LaunchAgent).

Layout after `install`:

    ~/Library/Application Support/mind-the-limit/
        app/mind_the_limit/     the program
        venv/                   Python with pyobjc-framework-IOBluetooth
        mind-the-limit          the command (a small shell script)
        config.json, state.json
    ~/Library/LaunchAgents/labs.simon-says.mind-the-limit.plist
    ~/Library/Logs/mind-the-limit.log

Nothing is deleted: `uninstall` and a reinstall move old files to the Trash.

Copyright (c) 2026 Simon Eckmiller. MIT License.
"""
from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from . import config, usage

PYOBJC = "pyobjc-framework-IOBluetooth==12.2.2"
MIN_PYTHON = (3, 10)
PYTHON_CANDIDATES = ["python3", "/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"]


def plist_path(home: Path = None) -> Path:
    if os.environ.get("MIND_THE_LIMIT_PLIST") and home is None:
        return Path(os.environ["MIND_THE_LIMIT_PLIST"])
    return (home or Path.home()) / "Library" / "LaunchAgents" / (config.LABEL + ".plist")


def venv_python(app_home: Path) -> Path:
    return app_home / "venv" / "bin" / "python"


def domain() -> str:
    return "gui/%d" % os.getuid()


def launchctl(*args, run=subprocess.run) -> int:
    return run(["launchctl"] + list(args), capture_output=True).returncode


def is_loaded(run=subprocess.run) -> bool:
    return launchctl("print", "%s/%s" % (domain(), config.LABEL), run=run) == 0


def python_ok(python: str, run=subprocess.run) -> bool:
    try:
        result = run([python, "-c", "import sys; print(sys.version_info[:2] >= %r)" % (MIN_PYTHON,)],
                     capture_output=True, text=True)
    except OSError:
        return False
    return result.returncode == 0 and result.stdout.strip() == "True"


def find_python(preferred: Optional[str] = None, run=subprocess.run, which=shutil.which) -> Optional[str]:
    if preferred:
        return preferred if python_ok(preferred, run) else None
    for candidate in [sys.executable] + PYTHON_CANDIDATES:
        path = candidate if os.path.isabs(candidate) else which(candidate)
        if path and python_ok(path, run):
            return path
    return None


def agent_plist(app_home: Path, log: Path, claude: Optional[str]) -> dict:
    paths: List[str] = []
    if claude:
        paths.append(str(Path(claude).parent))
    paths += [os.path.expanduser(p) for p in usage.EXTRA_PATHS] + ["/usr/bin", "/bin"]
    return {
        "Label": config.LABEL,
        "ProgramArguments": [str(venv_python(app_home)), "-m", "mind_the_limit", "run"],
        "EnvironmentVariables": {
            "PYTHONPATH": str(app_home / "app"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PATH": ":".join(dict.fromkeys(paths)),
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        "ProcessType": "Background",
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
    }


def _to_trash(path: Path, home: Path, tag: str) -> Path:
    target = home / ".Trash" / ("%s-%s-%s" % (config.NAME, tag, datetime.now().strftime("%Y-%m-%d_%H-%M-%S")))
    target.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(target / path.name))
    return target


def install(source: Path, python: str, with_agent: bool = True, run=subprocess.run, home: Path = None,
            say=print) -> int:
    home = home or Path.home()
    app_home = config.home()
    app_home.mkdir(parents=True, exist_ok=True)
    venv = app_home / "venv"
    if not venv_python(app_home).exists():
        if run([python, "-m", "venv", str(venv)]).returncode != 0:
            return 1
    if run([str(venv_python(app_home)), "-m", "pip", "install", "--disable-pip-version-check", "-q", PYOBJC]).returncode != 0:
        return 1
    target = app_home / "app" / "mind_the_limit"
    if target.exists():
        _to_trash(target, home, "old-program")
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    launcher = app_home / "mind-the-limit"
    launcher.write_text('#!/bin/sh\nPYTHONPATH="%s" exec "%s" -m mind_the_limit "$@"\n'
                        % (app_home / "app", venv_python(app_home)))
    launcher.chmod(0o755)
    cfg = config.load()
    if not cfg["claude"]:
        cfg["claude"] = usage.find_claude() or ""
    config.save(cfg)
    if with_agent:
        plist = plist_path(home)
        plist.parent.mkdir(parents=True, exist_ok=True)
        with open(plist, "wb") as handle:
            plistlib.dump(agent_plist(app_home, config.log_path(), cfg["claude"] or None), handle)
        if cfg["device"]:
            start(run)
    return 0


def start(run=subprocess.run) -> bool:
    plist = plist_path()
    launchctl("bootout", "%s/%s" % (domain(), config.LABEL), run=run)
    return launchctl("bootstrap", domain(), str(plist), run=run) == 0


def restart(run=subprocess.run) -> bool:
    if is_loaded(run):
        return launchctl("kickstart", "-k", "%s/%s" % (domain(), config.LABEL), run=run) == 0
    return plist_path().exists() and start(run)


def uninstall(run=subprocess.run, home: Path = None) -> Path:
    home = home or Path.home()
    launchctl("bootout", "%s/%s" % (domain(), config.LABEL), run=run)
    trash = None
    for path in (plist_path(home), config.home()):
        if path.exists():
            trash = _to_trash(path, home, "uninstalled")
    return trash or home / ".Trash"
