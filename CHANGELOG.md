# Changelog

All notable changes to Mind the Limit. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning: [Semantic Versioning](https://semver.org/).

## 1.0.0 - 2026-10-08

First public release. Grew out of a personal script that has shown the limits on a Timebox Evo since August 2026.

- Reads the limits from `claude -p /usage` (structured report first, text as fallback); costs no tokens.
- 16 x 16 panel: session, week and model week as number and bar; red symbols instead of stale numbers.
- Own Bluetooth layer for macOS 26: RFCOMM channel 1, answer check, reconnect by dropping the connection.
- Night window and optional Home Assistant entity that turns the box dark; token in the keychain.
- `install`, `find`, `set`, `connect-ha`, `run`, `preview`, `status`, `uninstall`; texts in five languages.
