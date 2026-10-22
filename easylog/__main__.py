import sys, os, argparse, datetime as dt
if not __package__:   # allow `python easylog ...` (running the folder directly)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import runpy; runpy.run_module("easylog", run_name="__main__", alter_sys=True); sys.exit()
from . import __version__, find_loggers, Logger, parse_config, export_csv, export_csv_type12
from .config_build import build_start, stop_config, check_params

def valid(cfg):
    return (cfg['name'].isprintable() and 0 < len(cfg['name']) and cfg['period'] > 0 and 0 <= cfg['samples'] <= 32768)

def state(c):
    on = bool(c[33] & 1); unread = bool(c[33] & 2)
    return "logging" if on else "stopped", "unread data" if unread else "no unread data"

TYPE_NAMES = {1: "EL-USB-1", 2: "EL-USB-1", 3: "USB-502"}

def table(rows, head):
    w = [max(len(str(r[i])) for r in [head] + rows) for i in range(len(head))]
    for r in [head, ["-" * x for x in w]] + rows:
        print("  ".join(str(v).ljust(x) for v, x in zip(r, w)).rstrip())

import textwrap
RAW = argparse.RawDescriptionHelpFormatter
SELECT = """
Selecting a logger:
  --serial N   pick the logger by serial number (see 'easylog list'). Preferred: index order can change.
  --index N    pick by the Index column of 'easylog list'.
  With only ONE logger connected you may omit both. With several, one is required."""

MAIN_EPILOG = """\
commands:
  list (-l)   show connected loggers: type, current measurement name, serial, state
  interactive (-i)  full-screen form to start a run with the arrow keys
  status      show one logger's settings and whether it is logging
  start       configure a logger and begin a new measurement run   (see: easylog start -h)
  stop        stop logging                                         (see: easylog stop -h)
  download    save the recorded data as a CSV file                 (see: easylog download -h)
  help        show this text

typical session:
  easylog list
  easylog start --serial 10070370 --name Downstairs --period 120 --unit F --yes
  easylog status                       (all loggers)
  easylog status --serial 10070370     (one logger)
  easylog stop --serial 10070370 --yes
  easylog download --serial 10070370 -o Downstairs.csv

Commands that change a logger (start, stop) only PRINT what they would do until you add --yes.
Run 'easylog <command> -h' for the details of each command."""

START_EPILOG = """\
REQUIRED
  --name TEXT      Name of this measurement run; it becomes the first CSV column header.
                   1-16 characters of printable ASCII: letters, digits, space (not first or last), and
                   ! # $ ' + - ; = @ [ ] ^ _ ` { } ~      NOT allowed: \\ " % & * , . / : < > ? | ( )
                   (the Windows app's own rule. The logger itself accepts any byte: 105 names tested.)
  --period SECS    Seconds between samples, whole number, 10 to 43200 (12 h; the vendor's documented range).
                   Hardware-tested so far: 10 s and 120 s.
  --unit F|C       Temperature unit stored in the logger and the CSV: F (Fahrenheit) or C (Celsius).

OPTIONAL: when to begin (choose at most one; default is immediately)
  --delay SECS     Start this many seconds from now (0 to 7 days = 604800).
  --start WHEN     Start at a clock time, local time: "YYYY-MM-DD HH:MM" or "YYYY-MM-DD HH:MM:SS".
                   Must be in the future, at most 7 days ahead.

OPTIONAL: safety
  --overwrite      Needed if the logger is currently logging or holds data you have not downloaded;
                   starting a new run ERASES that data. Download first (easylog download).
  --yes            Actually write to the logger. Without it, start only prints what it would do.
""" + SELECT + """

How long will it record?  Memory holds 16382 samples (USB-502, 2 bytes each: temp+humidity) and
16382 samples (EL-USB-1, temperature only). Run time = samples x period:
  period 10 s   -> about 45 hours        period 120 s -> about 22.7 days
  period 60 s   -> about 11.4 days       period 300 s -> about 56.9 days
Humidity is recorded by the USB-502 only; the EL-USB-1 records temperature only.

examples:
  Start now, every 2 minutes, Fahrenheit (preview only):
    easylog start --serial 10070370 --name Downstairs --period 120 --unit F
  Same, for real:
    easylog start --serial 10070370 --name Downstairs --period 120 --unit F --yes
  Start in 1 hour, every 10 seconds, Celsius:
    easylog start --serial 127069 --name Keggerator --period 10 --unit C --delay 3600 --yes
  Start tomorrow at 8:00 am, every 5 minutes:
    easylog start --serial 10070370 --name "Attic Test" --period 300 --unit F --start "2026-10-23 08:00" --yes
  Replace a run you have already downloaded (or don't need):
    easylog start --serial 127069 --name Keggerator --period 60 --unit F --overwrite --yes

After 'start --yes' the tool reads the logger back and confirms it is logging.
The USB-502's LEDs flash at each sample while it records."""

STOP_EPILOG = """\
Stops logging; the recorded data stays in the logger until a new run is started.
  --yes   Actually write to the logger. Without it, stop only prints what it would do.
""" + SELECT + """

examples:
  easylog stop --serial 10070370          (preview only)
  easylog stop --serial 10070370 --yes"""

DOWNLOAD_EPILOG = """\
Reads the recorded data and writes a CSV in the same format as the Windows EasyLog app
(header row: name, Time, temperature, humidity, dew point, serial number).
  -o FILE   output file name (default: <measurement name>.csv in the current directory)
""" + SELECT + """

EL-USB-1 only, when the logger's own settings are unreadable (e.g. after years without a battery).
Supply ALL of these together, as they were when the run was recorded:
  --name TEXT  --start "YYYY-MM-DDTHH:MM:SS"  --period SECS  --samples N  --unit F|C

examples:
  easylog download --serial 10070370 -o Downstairs.csv
  easylog download --serial 127069
  easylog download --serial 127069 --name Keggerator --start 2023-08-15T10:00:00 --period 60 --samples 8000 --unit F -o Keggerator.csv"""

STATUS_EPILOG = """\
Shows each logger's settings and state as a table: measurement name, running/stopped (or waiting to
start), temperature unit, interval, start time, samples recorded vs. memory capacity, time of the
last sample, when memory will be full, whether the data has been downloaded yet, and firmware if readable.
With no --serial/--index, ALL connected loggers are shown side by side.
""" + SELECT + """

example:
  easylog status --serial 10070370"""


CAPACITY = 16382   # samples; EL-USB-1 (1 byte each) and USB-502 (2 bytes each) both hold 16382

def human_secs(n):
    n = int(n); parts = []
    for unit, sec in (("d", 86400), ("h", 3600), ("min", 60), ("s", 1)):
        if n >= sec: parts.append(f"{n // sec} {unit}"); n %= sec
    return " ".join(parts[:2]) or "0 s"

def describe(c):
    """Column of human-readable status fields for one logger config block."""
    ser = int.from_bytes(c[52:56], 'little'); typ = TYPE_NAMES.get(c[0], f"type {c[0]} (unsupported)")
    cfg = parse_config(c) if c[0] in TYPE_NAMES else None
    f = {"Logger": typ, "Serial": ser}
    if not (cfg and valid(cfg)):
        f.update({"Measurement": "(unreadable config)"}); return f
    on, unread = state(c); n = cfg['samples']; per = cfg['period']; now = dt.datetime.now()
    status = on
    if on == "logging" and cfg['start'] > now: status = f"waiting to start ({cfg['start']:%Y-%m-%d %H:%M:%S})"
    f["Measurement"] = cfg['name']; f["State"] = status
    f["Temperature unit"] = "Fahrenheit" if cfg['fahrenheit'] else "Celsius"
    f["Interval"] = f"{per} s" + (f" ({human_secs(per)})" if per >= 60 else "")
    f["Started"] = cfg['start'].strftime('%Y-%m-%d %H:%M:%S')
    f["Samples recorded"] = f"{n} of {CAPACITY} ({100 * n / CAPACITY:.1f}%)"
    if n: f["Last sample"] = (cfg['start'] + dt.timedelta(seconds=(n - 1) * per)).strftime('%Y-%m-%d %H:%M:%S')
    if n: f["Recorded span"] = human_secs((n - 1) * per)
    if on == "logging": f["Memory full at"] = (cfg['start'] + dt.timedelta(seconds=(CAPACITY - 1) * per)).strftime('%Y-%m-%d %H:%M:%S')
    f["Unread data"] = "yes" if unread == "unread data" else "no"
    fw = cfg.get('firmware', '')
    if fw and fw.isprintable() and fw.isascii(): f["Firmware"] = fw
    return f

def status_table(configs):
    cols = [describe(c) for c in configs]
    canon = ["Logger", "Serial", "Measurement", "State", "Temperature unit", "Interval", "Started", "Samples recorded",
             "Last sample", "Recorded span", "Memory full at", "Unread data", "Firmware"]
    order = [k for k in canon if any(k in col for col in cols)]
    head = ["Setting"] + [f"{col['Logger']} {col['Serial']}" if len(cols) > 1 else "Value" for col in cols]
    table([[k] + [col.get(k, "") for col in cols] for k in order], head)

INTERACTIVE_EPILOG = """\
A full-screen form for starting a new run (same rules and limits as 'easylog start'):
  Logger            which connected logger (Left/Right to switch)
  Measurement Name  required, 1-16 printable ASCII characters
  Temperature unit  Fahrenheit or Celsius
  Interval          number; unit s / m / h (10 s to 12 h)
  Start Delay       number; unit s / m / h (0 = start now, up to 7 days)
Keys: Up/Down/Tab move, Left/Right or typing changes a choice, Enter accepts and moves on,
Esc quits. 'Review & start' shows a summary and asks y/n before anything is written.
If the logger is logging or holds undownloaded data you get an explicit warning first."""

class HelpOnErrorParser(argparse.ArgumentParser):
    """Usage errors print the message, then the full help for the command that was being parsed."""
    def error(self, message):
        sys.stderr.write(f"error: {message}\n\n")
        self.print_help(sys.stderr)
        sys.exit(2)

p = HelpOnErrorParser(prog="easylog", formatter_class=RAW, epilog=MAIN_EPILOG,
    description=f"easylog {__version__}: Lascar EasyLog USB loggers (EL-USB-1, USB-502) on macOS.   -l = list, -i = interactive, -v = version.")
p.add_argument("-v", "-V", "--version", action="version", version=f"easylog {__version__}")
sub = p.add_subparsers(dest="cmd", metavar="command")
sub.add_parser("list", help="show connected loggers (-l)")
sub.add_parser("interactive", help="fill in a start-a-run form with the arrow keys (-i)", formatter_class=RAW, epilog=INTERACTIVE_EPILOG)
sub.add_parser("help", help="show the overview and examples")
HELP = dict(status=("show a logger's settings and state", STATUS_EPILOG), stop=("stop logging", STOP_EPILOG),
            download=("save recorded data as CSV", DOWNLOAD_EPILOG), start=("configure and begin a new run", START_EPILOG))
for name in ("status", "start", "stop", "download"):
    sp = sub.add_parser(name, help=HELP[name][0], epilog=HELP[name][1], formatter_class=RAW)
    sp.add_argument("--serial", type=int, metavar="N", help="select logger by serial number (preferred)")
    sp.add_argument("--index", type=int, default=None, metavar="N", help="select logger by Index column of 'list'")
    if name in ("stop", "start"): sp.add_argument("--yes", action="store_true", help="actually write to the logger (otherwise preview only)")
    if name == "download":
        sp.add_argument("-o", metavar="FILE", help="output CSV file")
        for o in ("--name", "--start", "--period", "--samples", "--unit"): sp.add_argument(o, metavar="X", help=argparse.SUPPRESS)
    if name == "start":
        sp.add_argument("--name", required=True, metavar="TEXT", help="REQUIRED. run name, 1-16 printable ASCII chars (see below)")
        sp.add_argument("--period", type=int, required=True, metavar="SECS", help="REQUIRED. seconds between samples, 10-43200")
        sp.add_argument("--unit", choices=["F", "C"], type=str.upper, required=True, help="REQUIRED. temperature unit")
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--delay", type=int, metavar="SECS", help="start this many seconds from now (default: 0 = now)")
        g.add_argument("--start", metavar="WHEN", help='start at local time "YYYY-MM-DD HH:MM[:SS]"')
        sp.add_argument("--overwrite", action="store_true", help="allow replacing a run that is logging or has undownloaded data")
argv = [{'-l': 'list', '--list': 'list', '-i': 'interactive'}.get(x, x) if i == 0 else x for i, x in enumerate(sys.argv[1:])]   # -l == list, -i == interactive
a = p.parse_args(argv)
if a.cmd in (None, "help"):      # no command: show the help menu instead of an error
    p.print_help(); sys.exit()
devs = find_loggers()
if a.cmd == "list":
    rows = []
    for i, d in enumerate(devs):
        with Logger(d) as l: c = l.config()
        ser = int.from_bytes(c[52:56], 'little'); typ = TYPE_NAMES.get(c[0], f"type {c[0]} (unsupported)")
        cfg = parse_config(c) if c[0] in TYPE_NAMES else None
        if cfg and valid(cfg):
            on, _ = state(c); rows.append([i, typ, cfg['name'], ser, on, cfg['samples'], cfg['start'].strftime('%Y-%m-%d %H:%M:%S')])
        else: rows.append([i, typ, "(unreadable config)", ser, "?", "", ""])
    if not rows: print("no logger connected")
    else: table(rows, ["Index", "Logger", "Measurement", "Serial", "State", "Samples", "Started"])
    sys.exit()
if a.cmd == "interactive":
    from . import tui
    if not devs: sys.exit("no logger connected")
    infos, mapping = [], []
    for i, d in enumerate(devs):
        with Logger(d) as l: c = l.config()
        if c[0] not in (1, 2, 3): continue
        cfg = parse_config(c); ok = valid(cfg); on, unread = state(c)
        ser = int.from_bytes(c[52:56], 'little')
        infos.append(dict(label=f"{TYPE_NAMES[c[0]]} ({ser})", serial=ser, writable=True, name=cfg['name'] if ok else "(unreadable)",
                          fahrenheit=cfg['fahrenheit'] if ok else True, running=on == "logging", unread=unread == "unread data" and ok or (not ok), samples=cfg['samples'] if ok else 0))
        mapping.append(d)
    if not infos: sys.exit("no supported logger connected")
    def tui_write(req):
        with Logger(mapping[req["logger"]]) as l:
            c = l.config(); now = dt.datetime.now().replace(microsecond=0)
            problems = check_params(req["name"], req["period"], req["delay"])
            if problems: raise ValueError("; ".join(problems))
            ok, _ = l.write_config(build_start(c, req["name"], req["period"], req["fahrenheit"], now + dt.timedelta(seconds=req["delay"]), now))
            rb = l.config(); on, _u = state(rb); n = int.from_bytes(rb[30:32], 'little')
            out = [f"Write acknowledged: {ok}", f"Logger state: {on}, samples so far: {n}"]
            if not (rb[33] & 1): out.append("WARNING: logger did not enter logging state")
            else: out.append("Done. Check with: easylog status")
            return out
    res = tui.run(infos, tui_write)
    if res: print("\n".join(res))
    else: print("cancelled; nothing was written")
    sys.exit()
if a.cmd == "status" and a.serial is None and a.index is None:
    if not devs: sys.exit("no logger connected")
    cs = []
    for d in devs:
        with Logger(d) as l: cs.append(l.config())
    status_table(cs); sys.exit()
def pick():
    if a.serial is not None:
        for d in devs:
            with Logger(d) as l: c = l.config()
            if int.from_bytes(c[52:56], 'little') == a.serial: return d
        sys.exit(f"no logger with serial {a.serial} (try: python3 -m easylog list)")
    if len(devs) == 1 and a.index is None: return devs[0]
    if a.index is None: sys.exit("several loggers connected: pass --serial N (or --index N); see 'list'")
    if a.index >= len(devs): sys.exit("no such index")
    return devs[a.index]
if not devs: sys.exit("no logger connected")
with Logger(pick()) as l:
    c = l.config(); t = c[0]; cfg = parse_config(c) if t in (1,2,3,12,13,16) else None
    if cfg is None: sys.exit(f"logger type {t} not supported yet")
    if a.cmd == "status":
        status_table([c])
    elif a.cmd == "stop":
        if not a.yes: sys.exit(f"preview only: would stop logger {int.from_bytes(c[52:56], 'little')} ({cfg['name']}); add --yes to do it")
        if t not in (1, 2, 3): sys.exit("write support is implemented for types 1/2/3 only")
        ok, _ = l.write_config(stop_config(c)); print("stop ack:", ok); print(*state(l.config()))
    elif a.cmd == "start":
        if t not in (1, 2, 3): sys.exit("write support is implemented for types 1/2/3 only")
        now = dt.datetime.now().replace(microsecond=0)
        if a.start:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
                try: when = dt.datetime.strptime(a.start, fmt); break
                except ValueError: pass
            else: sys.exit('--start must look like "2026-10-23 08:00" (local time, YYYY-MM-DD HH:MM[:SS])')
        else: when = now + dt.timedelta(seconds=a.delay or 0)
        delay = int((when - now).total_seconds())
        problems = check_params(a.name, a.period, delay)
        if problems: sys.exit("cannot start:\n  " + "\n  ".join(problems) + "\n(see: easylog start -h)")
        on, unread = state(c)
        if (on == "logging" or unread == "unread data") and not a.overwrite:
            why = [x for x, f in (("is currently logging", on == "logging"), ("holds data that has not been downloaded", unread == "unread data")) if f]
            sys.exit("this logger " + " and ".join(why) + ": starting a new run would erase it.\n"
                     "Download it first (easylog download ...), or add --overwrite if you do not need it.")
        new = build_start(c, a.name, a.period, a.unit == "F", when, now)
        print(f"{'Starting' if a.yes else 'Would start'}: name '{a.name}', every {a.period} s, {'Fahrenheit' if a.unit == 'F' else 'Celsius'}, "
              + ("immediately" if delay == 0 else f"at {when:%Y-%m-%d %H:%M:%S} (in {delay} s)")
              + f"; erases the current run ('{cfg['name']}')")
        if not a.yes: sys.exit("preview only: add --yes to write to the logger")
        ok, _ = l.write_config(new); rb = l.config(); print("start ack:", ok); print(*state(rb), "samples", int.from_bytes(rb[30:32], 'little'))
        if not (rb[33] & 1): print("WARNING: logger did not enter logging state")
    else:  # download
        data = l.data()
        if t in (1, 2):
            if a.name or a.start or a.period or a.samples or a.unit:   # manual override for corrupted configs
                need = [k for k in ("name","start","period","samples","unit") if not getattr(a, k)]
                if need: sys.exit("override needs " + ", ".join("--"+k for k in need))
                cfg = dict(name=a.name, start=dt.datetime.fromisoformat(a.start), period=int(a.period), samples=int(a.samples),
                           fahrenheit=a.unit.upper()=="F", serial=cfg['serial'])
            elif not valid(cfg): sys.exit("config looks corrupt; supply --name --start --period --samples --unit")
            out = a.o or f"{cfg['name']}.csv"; export_csv_type12(cfg, data, out)
        else:
            out = a.o or f"{cfg['name']}.csv"; export_csv(cfg, data, out)
        print("wrote", out, cfg['samples'], "samples")
