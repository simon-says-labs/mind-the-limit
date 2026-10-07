"""The loop that runs in the background: read the limits, draw them, send them, keep the box awake.

Every reading replaces the picture. If the limits cannot be read, the box shows a red symbol
instead of the last numbers: old numbers that look current are worse than a visible gap.

Copyright (c) 2026 Simon Eckmiller. MIT License.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Dict, Optional

from . import __version__, brightness, config, panel, protocol, usage
from .device import DeviceError
from .texts import t

RETRY_SECONDS = 60


def _pct(value) -> str:
    return "%s%%" % (int(round(value)) if isinstance(value, float) else value)


class Runner:
    def __init__(self, cfg: Dict, box, lang: str, read_usage=usage.read_usage,
                 read_state: Optional[Callable[[], Optional[str]]] = None,
                 clock=time, log=print, state_file: Optional[Path] = None):
        self.cfg, self.box, self.lang = cfg, box, lang
        self.read_usage, self.read_state = read_usage, read_state or (lambda: None)
        self.clock, self.log, self.state_file = clock, log, state_file
        self.shown_brightness = None
        self.connected = False
        self.last_problem = None

    def say(self, key: str, **values) -> None:
        self.log("[%s] %s" % (self.clock.strftime("%H:%M:%S"), t(self.lang, key, **values)))

    def _write_state(self, **fields) -> None:
        if not self.state_file:
            return
        try:
            old = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old = {}
        old.update(fields)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(old, indent=2) + "\n", encoding="utf-8")

    def _ensure_connected(self) -> None:
        if not self.connected:
            self.box.connect()
            self.box.send(protocol.quiet(), settle=0.5)
            self.connected = True
            self.shown_brightness = None
            self.say("connected")

    def poll(self) -> list:
        """One reading. Returns the pixels that were sent."""
        stamp = self.clock.strftime("%Y-%m-%d %H:%M:%S")
        try:
            meters = self.read_usage(self.cfg.get("claude") or None)
            pixels = panel.render(meters, config.colors(self.cfg))
            names = {m.kind: m for m in meters}
            model = next((m for m in meters if m.kind == "model"), None)
            self.say("values", session=_pct(names["session"].percent) if "session" in names else "-",
                     week=_pct(names["week"].percent) if "week" in names else "-",
                     model="%s %s" % (model.label, _pct(model.percent)) if model else "-")
            self._write_state(time=stamp, meters=[m.__dict__ for m in meters], error=None)
            self.last_problem = None
        except usage.UsageUnavailable as exc:
            code = "claude" if exc.reason == "claude-missing" else "usage"
            pixels = panel.render_error(code)
            if exc.reason != self.last_problem:
                self.say("unavailable", reason=str(exc), symbol=panel.ERROR_SYMBOLS[code])
            self.last_problem = exc.reason
            self._write_state(error_time=stamp, error=str(exc), meters=[])
        self._ensure_connected()
        self.box.send(protocol.image(pixels), settle=0.5)
        return pixels

    def adjust_brightness(self) -> None:
        state = self.read_state()
        dark = brightness.is_dark(state, self.cfg.get("ha_dark_states"))
        hour = self.clock.localtime().tm_hour
        pct = brightness.target(hour, self.cfg, dark)
        if pct == self.shown_brightness:
            return
        self._ensure_connected()
        self.box.send(protocol.brightness(pct))
        if dark:
            why = t(self.lang, "why_dark", entity=self.cfg.get("ha_entity"), state=state)
        else:
            night = brightness.is_night(hour, int(self.cfg["night_start"]), int(self.cfg["night_end"]))
            why = t(self.lang, "why_night" if night else "why_day")
        self.say("brightness", pct=pct, why=why)
        self.shown_brightness = pct

    def cycle(self) -> None:
        """One reading, then wait for the next one: brightness and a keep-alive every minute."""
        try:
            self.poll()
            self.adjust_brightness()
        except DeviceError as exc:
            self.connected = False
            self.say("device_lost", error=exc, seconds=RETRY_SECONDS)
            self._write_state(error_time=self.clock.strftime("%Y-%m-%d %H:%M:%S"), error=str(exc))
            self.clock.sleep(RETRY_SECONDS)
            return
        remaining = int(self.cfg["interval"])
        while remaining > 0:
            step = min(60, remaining)
            self.clock.sleep(step)
            remaining -= step
            try:
                self.adjust_brightness()
                if remaining > 0 and not self.box.ping():
                    self.connected = False
            except DeviceError:
                self.connected = False

    def start_message(self) -> None:
        self.say("started", version=__version__, device=self.cfg["device"], interval=self.cfg["interval"],
                 night="%02d–%02d" % (self.cfg["night_start"], self.cfg["night_end"]),
                 night_pct=self.cfg["bright_night"],
                 ha=self.cfg["ha_entity"] or t(self.lang, "no"))
