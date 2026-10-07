"""Reads the Claude Code usage limits by running `claude -p /usage`.

`/usage` is a local command: it answers without calling a model, so asking costs no tokens
(measured with Claude Code 2.1.276: model "<synthetic>", total_cost_usd 0). The stream-json
output carries the limits twice: as a structured `usage_report` and as the text you see in
the terminal. The structured report is read first; the text is the fallback if the report is
missing or changes shape.

Copyright (c) 2026 Simon Eckmiller. MIT License.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional

KIND_ORDER = {"session": 0, "week": 1, "model": 2, "other": 3}

# Current session: 15% used · resets Oct 8 at 2:40am (Europe/Berlin)
# Current week (all models): 34% used · resets Oct 12 at 10pm (Europe/Berlin)
# Current week (Fable): 0% used · resets …
_LINE = re.compile(
    r"Current (?P<what>session|week)(?: \((?P<scope>[^)]*)\))?:\s*(?P<pct>\d+(?:\.\d+)?)%\s*used"
    r"(?:\s*·\s*resets\s+(?P<resets>[^\n]+))?",
    re.IGNORECASE)

# Where `claude` lives when it is not on the PATH of a background job.
EXTRA_PATHS = ["~/.local/bin", "~/.claude/local", "/opt/homebrew/bin", "/usr/local/bin"]


@dataclass(frozen=True)
class Meter:
    kind: str                 # session | week | model | other
    label: str                # "session", "all models", or the model's name
    percent: float
    resets_at: Optional[str] = None


class UsageUnavailable(Exception):
    """The limits could not be read. `reason` is one of claude-missing, claude-failed, no-limits."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__("%s: %s" % (reason, detail) if detail else reason)
        self.reason = reason
        self.detail = detail


def _from_report(limits) -> List[Meter]:
    meters = []
    for item in limits or []:
        if not isinstance(item, dict) or not isinstance(item.get("percent"), (int, float)):
            continue
        kind = item.get("kind", "")
        scope = item.get("scope") or {}
        model = ((scope.get("model") or {}).get("display_name")) if isinstance(scope, dict) else None
        if kind == "session":
            meters.append(Meter("session", "session", item["percent"], item.get("resets_at")))
        elif kind == "weekly_all":
            meters.append(Meter("week", "all models", item["percent"], item.get("resets_at")))
        elif kind == "weekly_scoped" and model:
            meters.append(Meter("model", model, item["percent"], item.get("resets_at")))
        else:
            meters.append(Meter("other", model or kind or "?", item["percent"], item.get("resets_at")))
    return meters


def parse_text(text: str) -> List[Meter]:
    """Reads the lines `Current …: N% used · resets …` from the text that /usage prints."""
    meters = []
    for m in _LINE.finditer(text or ""):
        what, scope = m.group("what").lower(), (m.group("scope") or "").strip()
        pct = float(m.group("pct"))
        pct = int(pct) if pct.is_integer() else pct
        resets = (m.group("resets") or "").strip() or None
        if what == "session":
            meters.append(Meter("session", "session", pct, resets))
        elif scope.lower() in ("", "all models"):
            meters.append(Meter("week", "all models", pct, resets))
        else:
            meters.append(Meter("model", scope, pct, resets))
    return meters


def _ordered(meters: List[Meter]) -> List[Meter]:
    return sorted(meters, key=lambda m: KIND_ORDER.get(m.kind, 9))  # stable: keeps text order within a kind


def parse_stream(output: str) -> List[Meter]:
    """Parses the stream-json output of `claude -p /usage`."""
    report, texts = None, []
    for line in (output or "").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "assistant":
            limits = ((event.get("usage_report") or {}).get("rate_limits") or {}).get("limits")
            if limits and report is None:
                report = limits
            for block in (event.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("text"):
                    texts.append(block["text"])
        elif event.get("type") == "result" and isinstance(event.get("result"), str):
            texts.append(event["result"])
    meters = _from_report(report)
    if not meters:
        for text in texts:
            meters = parse_text(text)
            if meters:
                break
    if not meters:
        raise UsageUnavailable("no-limits", " ".join(texts)[:200])
    return _ordered(meters)


def find_claude(configured: Optional[str] = None, which=shutil.which) -> Optional[str]:
    if configured:
        return configured
    path = os.pathsep.join([os.environ.get("PATH", "")] + [os.path.expanduser(p) for p in EXTRA_PATHS])
    return which("claude", path=path)


def read_usage(claude: Optional[str] = None, run=subprocess.run, which=shutil.which,
               timeout: int = 120) -> List[Meter]:
    """Runs `claude -p /usage` and returns the meters, session first."""
    exe = find_claude(claude, which)
    if not exe:
        raise UsageUnavailable("claude-missing")
    cmd = [exe, "-p", "/usage", "--output-format", "stream-json", "--verbose"]
    try:
        result = run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise UsageUnavailable("claude-failed", "no answer within %d s" % timeout)
    except OSError as exc:
        raise UsageUnavailable("claude-failed", str(exc))
    if result.returncode != 0:
        raise UsageUnavailable("claude-failed", (result.stderr or result.stdout or "").strip()[:200])
    return parse_stream(result.stdout)
