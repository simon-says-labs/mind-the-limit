"""How bright the panel should be: a night window, and optionally a Home Assistant entity
whose state turns the panel dark (for example "nobody home" or "all lights off").

If Home Assistant cannot be reached or the entity is unknown, the panel stays on: a dark
panel would hide that something is wrong.

Copyright (c) 2026 Simon Eckmiller. MIT License.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


def is_night(hour: int, start: int, end: int) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def target(hour: int, cfg: Dict[str, Any], dark: Optional[bool]) -> int:
    """Brightness in percent. `dark` is True when Home Assistant says the panel should be off."""
    if dark is True:
        return 0
    night = is_night(hour, int(cfg["night_start"]), int(cfg["night_end"]))
    return int(cfg["bright_night"] if night else cfg["bright_day"])


def entity_state(url: str, token: str, entity: str, opener=urllib.request.urlopen, timeout: float = 5) -> Optional[str]:
    """The entity's state, or None if Home Assistant does not answer or does not know it."""
    if not (url and token and entity):
        return None
    request = urllib.request.Request(
        "%s/api/states/%s" % (url.rstrip("/"), urllib.parse.quote(entity)),
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
    try:
        with opener(request, timeout=timeout) as response:
            state = json.loads(response.read().decode("utf-8")).get("state")
    except (urllib.error.URLError, OSError, ValueError, AttributeError):
        return None
    if state in (None, "unknown", "unavailable"):
        return None
    return str(state)


def is_dark(state: Optional[str], dark_states) -> Optional[bool]:
    if state is None:
        return None
    return state in (dark_states or [])
