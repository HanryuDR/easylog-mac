# easylog

A command-line tool for macOS to configure, start, stop and download Lascar EasyLog USB data
loggers. Lascar's software is Windows-only; this replaces it for the loggers below.

Version 1.2026-10-22. Python 3.9+, no pip packages.

| Logger   | USB type | Records                          | Tested |
|----------|----------|----------------------------------|--------|
| EL-USB-1 | 1 / 2    | temperature                      | yes    |
| USB-502  | 3        | temperature, humidity, dew point | yes    |

Other EasyLog models are not supported. The tool refuses to write to a logger type it has not
been tested on.

## Requirements

- macOS with [Homebrew](https://brew.sh) and libusb: `brew install libusb`
- Python 3.9 or newer (Homebrew Python is fine)
- A battery in the logger. The EL-USB-1 does not appear on USB without one.

pyusb is bundled in `easylog/_vendor`, so there is no `pip install` step.

## Install

    git clone <this repository>
    cd <repository>
    ./build.sh --install     # checks libusb (runs brew install libusb if needed),
                             # builds dist/easylog, copies it to /usr/local/bin/easylog

Or without installing, run from the repository folder: `python3 -m easylog list`

`./build.sh` alone only builds `dist/easylog`. `--no-libusb-check` skips the libusb check.
Rebuild after any code change; the built file is a snapshot of the source.

## Use

    easylog -l                       list connected loggers (alias of: list)
    easylog -i                       interactive form to start a run (alias of: interactive)
    easylog status [--serial N]      settings and state of every logger, or one
    easylog start  --serial N --name NAME --period SECS --unit F|C [--delay SECS] --yes
    easylog stop   --serial N --yes
    easylog download --serial N -o run.csv
    easylog -v                       version
    easylog help                     full help; every command also has -h

Always select a logger with `--serial`. The list index changes whenever a logger is plugged or
unplugged. `start` and `stop` only print what they would do until you add `--yes`. `start`
refuses to overwrite a logger that is logging or holds undownloaded data unless you pass
`--overwrite`.

Limits: name 1-16 printable ASCII characters (not `\ " % & * , . / : < > ? | ( )`, no leading
or trailing space); interval 10 s to 12 h; start delay up to 7 days. The interactive form takes
interval and delay as a number plus s / m / h, checks the same limits, and shows the
equivalent command line so you can repeat a run.

CSV output matches the Windows app's export format (Latin-1, CRLF, dew point included).

## Documentation

- `WRITE_PROTOCOL.md`: how configuration writes work, verified on hardware
- `PLAN.md`: protocol findings, probe results, published specs, parameter limits
- `probe/`: the small scripts used to read, decode and test the loggers

## Credits

This project was written by AI, working from hardware and a vendor application provided and
tested by its owner.

- **hermione** (☿): AI assistant, built on Nous Research's Hermes Agent. Wrote the code,
  documentation and tests, and ran the hardware tests.
- **Claude Sonnet** (Anthropic): the language model behind hermione.
- **REA**: the reverse-engineering workflow and tooling used to analyze the Windows application
  and the USB protocol (with ILSpy for .NET decompilation).
- **Daniel**: project owner. Supplied the loggers, directed the work and tested the results.

Bundled third-party code: [PyUSB](https://github.com/pyusb/pyusb) 1.3.1 (BSD 3-clause), in
`easylog/_vendor`; license in `easylog/_vendor/LICENSE-pyusb.txt`.

## Disclaimer

Unofficial and unaffiliated with Lascar Electronics. "Lascar" and "EasyLog" are their
trademarks. No vendor software, installers or decompiled code are included in this repository;
the protocol was worked out by analyzing a copy of the vendor's Windows application for
interoperability, and checked against data the vendor's software saved. This tool writes to
the logger's configuration memory. Use it at your own risk; it has been tested only on the
two loggers above.

## License and contributing

easylog is free software under the GNU General Public License v3 (see `LICENSE`). You can
use, study, change and share it; if you distribute a modified version, it has to stay under
the GPL with its source available. The bundled PyUSB keeps its own BSD 3-clause license
(`easylog/_vendor/LICENSE-pyusb.txt`), which is compatible with the GPL.

Contributions are welcome: bug reports, support for other EasyLog models, and results from
other loggers or macOS versions. Please keep vendor software, installers and decompiled code
out of pull requests. Contributions are accepted under the same license.
