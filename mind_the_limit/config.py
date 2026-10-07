"""Settings and file locations.

Everything lives outside synced folders: settings and the program in
~/Library/Application Support/mind-the-limit, the log in ~/Library/Logs/mind-the-limit.log.
The Home Assistant token is not a setting; it lives in the keychain (keychain.py).

Copyright (c) 2026 Simon Eckmiller. MIT License.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict

NAME = "mind-the-limit"
LABEL = "labs.simon-says.mind-the-limit"

DEFAULTS: Dict[str, Any] = {
    "device": "",              # Bluetooth address of the Timebox Evo, e.g. 11-22-33-44-55-66
    "interval": 300,           # seconds between two readings of the limits
    "night_start": 23,         # full hour
    "night_end": 7,            # full hour
    "bright_day": 60,          # percent
    "bright_night": 10,        # percent
    "ha_url": "",              # e.g. http://homeassistant.local:8123
    "ha_entity": "",           # e.g. binary_sensor.someone_home
    "ha_dark_states": ["off", "not_home"],
    "claude": "",              # path to the claude command; empty = search
    "language": "auto",
    "colors": {},              # e.g. {"session": "#FFFFFF"}
}

_ADDRESS = re.compile(r"^[0-9A-Fa-f]{2}([-:][0-9A-Fa-f]{2}){5}$")
_COLOR = re.compile(r"^#?[0-9A-Fa-f]{6}$")


def home() -> Path:
    return Path(os.environ.get("MIND_THE_LIMIT_HOME") or Path.home() / "Library" / "Application Support" / NAME)


def log_path() -> Path:
    return Path(os.environ.get("MIND_THE_LIMIT_LOG") or Path.home() / "Library" / "Logs" / (NAME + ".log"))


def config_path() -> Path:
    return home() / "config.json"


def state_path() -> Path:
    return home() / "state.json"


def load(path: Path = None) -> Dict[str, Any]:
    path = path or config_path()
    try:
        stored = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stored = {}
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in stored.items() if k in DEFAULTS})
    return cfg


def save(cfg: Dict[str, Any], path: Path = None) -> Path:
    path = Path(path or config_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({k: cfg[k] for k in DEFAULTS if k in cfg}, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def colors(cfg: Dict[str, Any]) -> Dict[str, int]:
    return {k: int(v.lstrip("#"), 16) for k, v in (cfg.get("colors") or {}).items() if _COLOR.match(str(v))}


def parse_value(key: str, raw: str) -> Any:
    """Turns `set KEY VALUE` input into a stored value; raises ValueError with a short reason."""
    if key == "device":
        if not _ADDRESS.match(raw):
            raise ValueError("address")
        return raw.upper().replace(":", "-")
    if key == "interval":
        value = int(raw)
        if value < 60:
            raise ValueError("interval")
        return value
    if key in ("night_start", "night_end"):
        value = int(raw)
        if not 0 <= value <= 23:
            raise ValueError("hour")
        return value
    if key in ("bright_day", "bright_night"):
        value = int(raw)
        if not 0 <= value <= 100:
            raise ValueError("percent")
        return value
    if key == "ha_dark_states":
        return [s.strip() for s in raw.split(",") if s.strip()]
    if key.startswith("colors."):
        if key[7:] not in ("session", "week", "model", "other") or not _COLOR.match(raw):
            raise ValueError("color")
        return "#" + raw.lstrip("#").upper()
    if key in ("ha_url", "ha_entity", "claude", "language"):
        return raw.strip()
    raise ValueError("key")


def set_value(cfg: Dict[str, Any], key: str, raw: str) -> Dict[str, Any]:
    value = parse_value(key, raw)
    cfg = dict(cfg)
    if key.startswith("colors."):
        cfg["colors"] = dict(cfg.get("colors") or {}, **{key[7:]: value})
    else:
        cfg[key] = value
    return cfg
