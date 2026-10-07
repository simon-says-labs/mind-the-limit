"""mind-the-limit — your Claude Code usage limits on a Divoom Timebox Evo.

    install [--python P] [--no-agent]   program, Python environment and background job
    find                                 paired Bluetooth devices with their addresses
    set KEY VALUE                        change a setting (device, interval, night_start, …)
    connect-ha [--from-env URL TOKEN] [--entity E] | --forget
    run [--once]                         the loop the background job runs
    preview [--out FILE] [--values 15,34,0 | --error usage|claude]
    status
    uninstall

Copyright (c) 2026 Simon Eckmiller. MIT License.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, agent, brightness, config, homeassistant, keychain, panel, usage
from .texts import t, language


def _lang(cfg, override=None):
    return language(override or cfg.get("language", "auto"))


def cmd_install(args, cfg, lang) -> int:
    if sys.platform != "darwin":
        print(t(lang, "not_macos"))
        return 2
    python = agent.find_python(args.python)
    if not python:
        print(t(lang, "no_python"))
        return 2
    print(t(lang, "installing", path=config.home()))
    code = agent.install(Path(__file__).resolve().parent, python, with_agent=not args.no_agent)
    if code == 0:
        cfg = config.load()
        state = t(lang, "agent_started") if cfg["device"] and not args.no_agent else t(lang, "agent_waiting")
        print(t(lang, "installed", label=config.LABEL, state=state))
        if not cfg["device"]:
            print(t(lang, "no_device"))
    return code


def cmd_find(args, cfg, lang) -> int:
    from .device import paired_devices
    devices = paired_devices()
    if not devices:
        print(t(lang, "find_none"))
        return 1
    for name, address in devices:
        print("%s  %s" % (address, name))
    return 0


def cmd_set(args, cfg, lang) -> int:
    try:
        cfg = config.set_value(cfg, args.key, args.value)
    except ValueError:
        print(t(lang, "set_invalid", key=args.key, value=args.value))
        return 2
    config.save(cfg)
    shown = cfg["colors"].get(args.key[7:]) if args.key.startswith("colors.") else cfg[args.key]
    print(t(lang, "set_done", key=args.key, value=shown))
    if sys.platform == "darwin" and agent.plist_path().exists():
        agent.restart()
    return 0


def cmd_connect_ha(args, cfg, lang) -> int:
    if args.forget:
        return homeassistant.forget(lang)
    code = homeassistant.connect(lang, from_env=args.from_env, entity=args.entity or "")
    if code == 0 and sys.platform == "darwin" and agent.plist_path().exists():
        agent.restart()
    return code


def _entity_reader(cfg):
    token = {"value": None}

    def read():
        if not (cfg["ha_url"] and cfg["ha_entity"]):
            return None
        if token["value"] is None:
            token["value"] = keychain.read_token()
        return brightness.entity_state(cfg["ha_url"], token["value"], cfg["ha_entity"])
    return read


def cmd_run(args, cfg, lang) -> int:
    from .device import MacLink, Timebox
    from .runner import Runner
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)  # log lines appear at once under launchd
    if not cfg["device"]:
        print(t(lang, "no_device"))
        return 2
    box = Timebox(MacLink(cfg["device"]), log=lambda m: print("  bluetooth: %s" % m))
    runner = Runner(cfg, box, lang, read_state=_entity_reader(cfg), state_file=config.state_path())
    if args.once:
        runner.poll()
        runner.adjust_brightness()
        box.close()
        return 0
    runner.start_message()
    try:
        while True:
            runner.cycle()
    except KeyboardInterrupt:
        box.close()
        return 0


def cmd_preview(args, cfg, lang) -> int:
    if args.error:
        pixels = panel.render_error(args.error)
    elif args.values:
        numbers = [float(v) for v in args.values.split(",")]
        kinds = [("session", "session"), ("week", "all models"), ("model", "model")]
        pixels = panel.render([usage.Meter(k, label, n) for (k, label), n in zip(kinds, numbers)], config.colors(cfg))
    else:
        pixels = panel.render(usage.read_usage(cfg["claude"] or None), config.colors(cfg))
    path = panel.to_png(pixels, Path(args.out), scale=args.scale)
    print(t(lang, "preview_written", path=path))
    return 0


def cmd_status(args, cfg, lang) -> int:
    print("Mind the Limit %s" % __version__)
    running = sys.platform == "darwin" and agent.is_loaded()
    print(t(lang, "status_agent", state=t(lang, "status_running" if running else "status_stopped")))
    print("device=%s interval=%s ha=%s" % (cfg["device"] or "-", cfg["interval"], cfg["ha_entity"] or "-"))
    try:
        state = json.loads(config.state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if state.get("meters"):
        values = " | ".join("%s %s%%" % (m["label"], m["percent"]) for m in state["meters"])
        print(t(lang, "status_last", time=state.get("time"), values=values))
    elif not state.get("error"):
        print(t(lang, "status_none"))
    if state.get("error"):
        print(t(lang, "status_error", time=state.get("error_time"), error=state["error"]))
    print("log: %s" % config.log_path())
    return 0


def cmd_uninstall(args, cfg, lang) -> int:
    print(t(lang, "uninstalled", path=agent.uninstall()))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="mind-the-limit", description="Simon says: mind the limit!")
    parser.add_argument("--language", choices=("en", "de", "fr", "it", "es"))
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("install")
    p.add_argument("--python")
    p.add_argument("--no-agent", action="store_true")
    sub.add_parser("find")
    p = sub.add_parser("set")
    p.add_argument("key")
    p.add_argument("value")
    p = sub.add_parser("connect-ha")
    p.add_argument("--from-env", nargs=2, metavar=("URL_VAR", "TOKEN_VAR"))
    p.add_argument("--entity")
    p.add_argument("--forget", action="store_true")
    p = sub.add_parser("run")
    p.add_argument("--once", action="store_true")
    p = sub.add_parser("preview")
    p.add_argument("--out", default="mind-the-limit-preview.png")
    p.add_argument("--values")
    p.add_argument("--error", choices=("usage", "claude"))
    p.add_argument("--scale", type=int, default=20)
    sub.add_parser("status")
    sub.add_parser("uninstall")
    args = parser.parse_args(argv)
    cfg = config.load()
    lang = _lang(cfg, args.language)
    handler = {"install": cmd_install, "find": cmd_find, "set": cmd_set, "connect-ha": cmd_connect_ha,
               "run": cmd_run, "preview": cmd_preview, "status": cmd_status, "uninstall": cmd_uninstall}
    return handler[args.command](args, cfg, lang)


if __name__ == "__main__":
    sys.exit(main())
