# Security policy

Only the latest release receives fixes. Please report vulnerabilities through
[GitHub's private vulnerability reporting](https://github.com/simon-says-labs/mind-the-limit/security/advisories/new),
not in public issues.

## What Mind the Limit does on your Mac

- It runs as your user, never with `sudo`, as a LaunchAgent (`labs.simon-says.mind-the-limit`).
- It runs `claude -p /usage`, Apple's `security` (keychain) and `launchctl`, always directly, never through a shell.
- It talks to one Bluetooth device, the address you set, on RFCOMM channel 1.
- If you connect Home Assistant, it reads one entity's state with a long-lived token. The token lives in the macOS
  keychain (service `mind-the-limit`) and is handed to `security` on standard input, never as a command argument,
  so it does not appear in the process list, in files or in the log.
- `install` downloads `pyobjc-framework-IOBluetooth` (pinned version) from PyPI into its own environment.
- Nothing is deleted: an older program version and `uninstall` go to the Trash.
