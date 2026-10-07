# Contributing

Thanks for your interest in Mind the Limit. Bug reports, ideas and pull requests are welcome.

## Reporting a bug

Open an [issue](https://github.com/simon-says-labs/mind-the-limit/issues) with your macOS and Claude Code versions
(`claude --version`), what you expected and what happened, and the lines around the problem from
`~/Library/Logs/mind-the-limit.log`. Please remove the Bluetooth address and anything else you do not want to share.

If the box shows a red `?`, the output of `claude -p /usage --output-format stream-json --verbose` helps most.

## Development

The tests need no Bluetooth and no Claude Code: `tests/fakes.py` stands in for the connection to the box, and the
real `/usage` output is a fixture in `tests/fixtures/`.

```bash
python3 -m unittest discover -s tests -t .
python3 -m mind_the_limit preview --values 23,35,0 --out panel.png
```

| File | Does |
|---|---|
| `mind_the_limit/usage.py` | runs `claude -p /usage` and reads the limits |
| `mind_the_limit/panel.py` | draws the 16 x 16 picture, error symbols and PNG previews |
| `mind_the_limit/protocol.py` | encodes messages for the Timebox Evo |
| `mind_the_limit/device.py` | the Bluetooth link: retries, reconnect, keep-alive |
| `mind_the_limit/brightness.py` | night window and Home Assistant entity |
| `mind_the_limit/runner.py` | the background loop |
| `mind_the_limit/agent.py`, `homeassistant.py`, `keychain.py` | install, Home Assistant assistant, keychain |
| `mind_the_limit/texts.py` | everything the program says, in five languages |

## Pull requests

- One topic per pull request, with a test that fails without your change.
- Texts need all five languages in `texts.py`; the tests check it.
- Everything except `device.MacLink` stays on the standard library and Python 3.9.
- Add a line to `CHANGELOG.md` under an `Unreleased` heading.
