"""Connects Mind the Limit to Home Assistant, step by step (`mind-the-limit connect-ha`).

1. Asks for the address and checks that Home Assistant answers there.
2. Opens your profile's security page, where you create a long-lived token.
3. You paste the token; the input stays hidden. It is checked and stored in the keychain.
4. You name the entity whose state turns the panel dark; it is checked too.

`--from-env URL_VAR TOKEN_VAR` does the same without questions, for scripts.

Copyright (c) 2026 Simon Eckmiller. MIT License.
"""
from __future__ import annotations

import getpass
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

from . import config, keychain
from .texts import t

DEFAULT_URL = "http://homeassistant.local:8123"


def call(url: str, path: str, token: str = "", opener=urllib.request.urlopen):
    """(status, json or None). Status 0 = no answer."""
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url.rstrip("/") + path, headers=headers)
    try:
        with opener(request, timeout=8) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as error:
        error.close()
        return error.code, None
    except (urllib.error.URLError, OSError, ValueError):
        return 0, None


def check(url: str, token: str, entity: str, opener=urllib.request.urlopen) -> str:
    """'' if everything works, else the text key of the problem."""
    status, _ = call(url, "/api/", opener=opener)
    if status not in (200, 401):
        return "ha_unreachable"
    status, _ = call(url, "/api/", token, opener=opener)
    if status != 200:
        return "ha_rejected"
    status, _ = call(url, "/api/states/" + urllib.parse.quote(entity), token, opener=opener)
    if status != 200:
        return "ha_entity_unknown"
    return ""


def connect(lang: str, from_env=None, entity: str = "", opener=urllib.request.urlopen, ask=input,
            ask_secret=getpass.getpass, browser=webbrowser.open, say=print, store=keychain.store_token) -> int:
    cfg = config.load()
    if from_env:
        url_var, token_var = from_env
        url, token = os.environ.get(url_var, "").strip(), os.environ.get(token_var, "").strip()
        for name, value in ((url_var, url), (token_var, token)):
            if not value:
                say(t(lang, "ha_env_missing", name=name))
                return 2
    else:
        say(t(lang, "ha_intro"))
        url = (ask(t(lang, "ha_url", default=cfg["ha_url"] or DEFAULT_URL)).strip() or cfg["ha_url"] or DEFAULT_URL)
        if call(url, "/api/", opener=opener)[0] not in (200, 401):
            say(t(lang, "ha_unreachable", url=url))
            return 1
        page = url.rstrip("/") + "/profile/security"
        say(t(lang, "ha_browser", url=page))
        browser(page)
        token = ask_secret(t(lang, "ha_token")).strip()
        entity = entity or ask(t(lang, "ha_entity")).strip()
    entity = entity or cfg["ha_entity"]
    problem = check(url, token, entity, opener)
    if problem:
        say(t(lang, problem, url=url, entity=entity))
        return 1
    store(token)
    cfg.update(ha_url=url.rstrip("/"), ha_entity=entity)
    config.save(cfg)
    say(t(lang, "ha_saved", entity=entity))
    return 0


def forget(lang: str, say=print, forget_token=keychain.forget_token) -> int:
    forget_token()
    cfg = config.load()
    cfg.update(ha_url="", ha_entity="")
    config.save(cfg)
    say(t(lang, "ha_forgotten"))
    return 0
