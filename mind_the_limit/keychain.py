"""Keeps the Home Assistant token in the macOS keychain, through Apple's `security` command.

The token is handed to `security` on its standard input (`security -i`), never as a command
argument, so it does not show up in the process list. It is never written to a file, a log or
the screen.

Copyright (c) 2026 Simon Eckmiller. MIT License.
"""
from __future__ import annotations

import re
import subprocess

SERVICE = "mind-the-limit"
ACCOUNT = "home-assistant"
_SAFE = re.compile(r"^[A-Za-z0-9._\-]+$")   # long-lived tokens are JWTs: letters, digits, dot, dash, underscore


class KeychainError(Exception):
    pass


def read_token(run=subprocess.run) -> str:
    result = run(["security", "find-generic-password", "-s", SERVICE, "-a", ACCOUNT, "-w"],
                 capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def store_token(token: str, run=subprocess.run) -> None:
    if not _SAFE.match(token or ""):
        raise KeychainError("token")
    result = run(["security", "-i"], input="add-generic-password -U -s %s -a %s -w %s\n" % (SERVICE, ACCOUNT, token),
                 capture_output=True, text=True)
    if result.returncode != 0 or read_token(run) != token:
        raise KeychainError("store")


def forget_token(run=subprocess.run) -> bool:
    result = run(["security", "delete-generic-password", "-s", SERVICE, "-a", ACCOUNT],
                 capture_output=True, text=True)
    return result.returncode == 0
