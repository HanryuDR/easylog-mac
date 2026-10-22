"""Interactive start-a-run form (curses, stdlib only).

Form is pure state + rendering (no curses, no USB) so it can be unit-tested; run() is the thin curses shell.
Keys (normalized names): UP DOWN LEFT RIGHT TAB BTAB ENTER BACKSPACE ESC or a single character.
"""
import os, shlex, textwrap, datetime as dt
from .config_build import check_params, PERIOD_MIN_S, PERIOD_MAX_S, NAME_MAX_LEN

MULT = {"s": 1, "m": 60, "h": 3600}
CAPACITY = 16382
LABEL_W, VALUE_W = 16, 28

def human(n):
    n = int(n); parts = []
    for unit, sec in (("d", 86400), ("h", 3600), ("min", 60), ("s", 1)):
        if n >= sec: parts.append(f"{n // sec} {unit}"); n %= sec
    return " ".join(parts[:2]) or "0 s"

class Form:
    # (key, label, kind, hint)
    FIELDS = [
        ("logger", "Logger", "choice", "Which connected logger to configure. Left/Right changes it."),
        ("name", "Measurement Name", "text", f"1-{NAME_MAX_LEN} printable ASCII characters; not allowed: \\ \" % & * , . / : < > ? | ( )  and no leading/trailing space."),
        ("temp", "Temperature unit", "choice", "Left/Right or type F / C."),
        ("interval", "Interval", "number", f"Time between samples. Allowed {PERIOD_MIN_S} s to {PERIOD_MAX_S // 3600} h (vendor range)."),
        ("iunit", "Interval unit", "choice", "Left/Right or type s / m / h  (seconds, minutes, hours)."),
        ("delay", "Start Delay", "number", "How long to wait before the first sample. 0 = start immediately. Up to 7 days."),
        ("dunit", "Start Unit", "choice", "Left/Right or type s / m / h  (seconds, minutes, hours)."),
    ]
    CHOICES = {"temp": ["Fahrenheit", "Celsius"], "iunit": ["s", "m", "h"], "dunit": ["s", "m", "h"]}

    def __init__(self, loggers):
        """loggers: list of dicts: label, serial, writable, name, fahrenheit, period, running, unread, samples."""
        self.loggers = loggers
        self.v = {"logger": 0, "name": "", "temp": 0, "interval": "10", "iunit": 0, "delay": "0", "dunit": 1}   # choices stored as indexes
        self.focus = 0
        self.stage = "edit"          # edit -> confirm -> done
        self.message = ""
        self.result = []
        self.last_command = None
        self._prefill()

    # ---- prefill from the selected logger's current run
    def _prefill(self):
        lg = self.loggers[self.v["logger"]]
        self.v["temp"] = 0 if lg.get("fahrenheit", True) else 1

    @property
    def n_rows(self): return len(self.FIELDS) + 1      # + the Start row

    @property
    def on_action(self): return self.focus == len(self.FIELDS)

    def cur(self): return None if self.on_action else self.FIELDS[self.focus]

    # ---- values
    def display(self, key):
        if key == "logger": return self.loggers[self.v["logger"]]["label"]
        if key in self.CHOICES: return self.CHOICES[key][self.v[key]]
        return self.v[key]

    def seconds(self, num, unit):
        s = str(self.v[num]).strip()
        return int(s) * MULT[self.CHOICES[unit][self.v[unit]]] if s.isdigit() else None

    def validate(self):
        """-> (errors, request or None)."""
        errors = []
        lg = self.loggers[self.v["logger"]]
        if not lg.get("writable", True): errors.append("this logger type cannot be configured yet")
        period = self.seconds("interval", "iunit"); delay = self.seconds("delay", "dunit")
        if period is None: errors.append("Interval must be a whole number")
        if delay is None: errors.append("Start Delay must be a whole number (0 = now)")
        name = self.v["name"]
        if not name: errors.append("Measurement Name is required")
        if period is not None and delay is not None:
            errors += [e for e in check_params(name or "x", period, delay)]
        elif name:
            errors += [e for e in check_params(name, PERIOD_MIN_S, 0) if e.startswith("name")]
        if errors: return errors, None
        return [], dict(logger=self.v["logger"], name=name, period=period, delay=delay,
                        fahrenheit=self.CHOICES["temp"][self.v["temp"]] == "Fahrenheit")

    def command(self, req):
        """Equivalent non-interactive command (seconds throughout; --overwrite only when needed)."""
        lg = self.loggers[req["logger"]]
        parts = ["python3", "-m", "easylog", "start", "--serial", str(lg["serial"]), "--name", shlex.quote(req["name"]),
                 "--period", str(req["period"]), "--unit", "F" if req["fahrenheit"] else "C"]
        if req["delay"]: parts += ["--delay", str(req["delay"])]
        if lg.get("running") or lg.get("unread"): parts.append("--overwrite")
        return " ".join(parts + ["--yes"])

    def preview(self, req):
        lg = self.loggers[req["logger"]]
        when = "immediately" if req["delay"] == 0 else f"in {human(req['delay'])} (at {dt.datetime.now() + dt.timedelta(seconds=req['delay']):%H:%M:%S})"
        full = human((CAPACITY - 1) * req["period"])
        return f"{lg['label']}: '{req['name']}', every {human(req['period'])}, {'F' if req['fahrenheit'] else 'C'}, start {when}; memory lasts {full}"

    # ---- key handling. returns None, or ("quit",) / ("write", request)
    def key(self, k):
        if self.stage == "done": return ("quit",)
        if self.stage == "confirm":
            if k in ("y", "Y"): return ("write", self.pending)
            if k in ("n", "N", "ESC", "q", "BACKSPACE"): self.stage = "edit"; self.message = ""
            return None
        self.message = ""
        if k == "ESC" or (k == "q" and self.on_action): return ("quit",)
        if k in ("UP", "BTAB"): self.focus = (self.focus - 1) % self.n_rows; return None
        if k in ("DOWN", "TAB"): self.focus = (self.focus + 1) % self.n_rows; return None
        if k == "ENTER":
            if not self.on_action:
                self.focus = (self.focus + 1) % self.n_rows; return None
            errors, req = self.validate()
            if errors: self.message = "Cannot start: " + "; ".join(errors); return None
            self.pending = req; self.stage = "confirm"; return None
        f = self.cur()
        if f is None: return None
        key, _, kind, _ = f
        if kind == "choice":
            opts = self.loggers if key == "logger" else self.CHOICES[key]
            n = len(opts)
            if k == "LEFT": self.v[key] = (self.v[key] - 1) % n
            elif k in ("RIGHT", " "): self.v[key] = (self.v[key] + 1) % n
            elif len(k) == 1 and key != "logger":
                for i, o in enumerate(opts):
                    if o.lower().startswith(k.lower()): self.v[key] = i; break
            if key == "logger": self._prefill()
        elif kind == "text":
            if k == "BACKSPACE": self.v[key] = self.v[key][:-1]
            elif len(k) == 1 and k.isprintable() and len(self.v[key]) < 40: self.v[key] += k   # length checked by validate (shows why)
        elif kind == "number":
            if k == "BACKSPACE": self.v[key] = self.v[key][:-1]
            elif len(k) == 1 and k.isdigit() and len(self.v[key]) < 7: self.v[key] += k
            elif k in ("LEFT", "RIGHT"): pass
        return None

    # ---- rendering: list of (text, style); style in {"", "head", "sel", "err", "warn", "ok", "dim"}; plus (y, x) cursor or None
    def render(self):
        L = []
        if self.stage == "confirm":
            req = self.pending; lg = self.loggers[req["logger"]]
            L += [("Review", "head"), ("", ""), (f"  Logger        {lg['label']}", ""), (f"  Name          {req['name']}", ""),
                  (f"  Interval      {human(req['period'])}", ""), (f"  Temperature   {'Fahrenheit' if req['fahrenheit'] else 'Celsius'}", ""),
                  (f"  Start         {'immediately' if req['delay'] == 0 else 'in ' + human(req['delay'])}", ""),
                  (f"  Memory lasts  {human((CAPACITY - 1) * req['period'])} ({CAPACITY} samples)", ""), ("", "")]
            if lg.get("running") or lg.get("unread"):
                why = " and ".join(x for x, f in (("is logging", lg.get("running")), ("holds data you have not downloaded", lg.get("unread"))) if f)
                L += [(f"  WARNING: this logger {why} (current run: '{lg.get('name', '')}').", "warn"),
                      ("  Starting a new run ERASES that data.", "warn"), ("", "")]
            L += [("  Command:  " + self.command(req), "cmd"), ("", "")]
            L += [("  y = write to the logger        n / Esc = go back", "ok")]
            return L, None
        if self.stage == "done":
            return [("Result", "head"), ("", "")] + [("  " + r, "ok" if not r.startswith("WARNING") else "err") for r in self.result] + [("", ""), ("  Press any key to exit.", "dim")], None
        cursor = None
        lg = self.loggers[self.v["logger"]]
        L.append(("easylog: configure a new run", "head")); L.append(("", ""))
        # logger row (above the table, like the mock-up)
        sel = self.focus == 0
        L.append((f"{'Logger':<{LABEL_W}}  " + self._cell(0, sel), "row" if not sel else "rowsel"))
        L.append(("", ""))
        L.append((f"{'Setting':<{LABEL_W}}  {'Value':<{VALUE_W}}", "head")); L.append((f"{'-' * LABEL_W}  {'-' * VALUE_W}", ""))
        for i in range(1, len(self.FIELDS)):
            sel = self.focus == i
            L.append((f"{self.FIELDS[i][1]:<{LABEL_W}}  " + self._cell(i, sel), "rowsel" if sel else "row"))
        L.append(("", ""))
        L.append(("[ Review & start ]" if not self.on_action else "[ Review & start ]  <- press Enter", "rowsel" if self.on_action else "row"))
        L.append(("", ""))
        L.append((("  " + self.FIELDS[self.focus][3]) if not self.on_action else "  Checks your settings, then asks for confirmation before writing anything.", "dim"))
        L.append(("", ""))
        errors, req = self.validate()
        if self.message: L.append(("  " + self.message, "err"))
        elif errors: L.append(("  Not ready: " + "; ".join(errors), "warn"))
        else: L.append(("  Ready: " + self.preview(req), "ok"))
        L.append(("", ""))
        L.append(("Equivalent command (copy/paste to repeat):", "head"))
        if not errors: self.last_command = self.command(req)
        L.append(("  " + (self.command(req) if not errors else "(complete the form to see the command)"), "cmd" if not errors else "dim"))
        L.append(("", ""))
        L.append(("  Up/Down/Tab move   Left/Right change choice   type to edit   Enter next/accept   Esc quit", "dim"))
        # cursor position for text/number rows
        f = self.cur()
        if f and f[2] in ("text", "number"):
            row = 2 + (self.focus if self.focus == 0 else self.focus + 2)
            cursor = (row, LABEL_W + 2 + len(self.v[f[0]]))
        return L, cursor

    def _cell(self, i, sel):
        key, _, kind, _ = self.FIELDS[i]
        t = self.display(key)
        if kind == "choice" and sel: t = f"< {t} >"
        return f"{t:<{VALUE_W}}"


KEYPAD = {**{chr(ord("p") + i): str(i) for i in range(10)}, "M": "ENTER", "m": "-", "l": ",", "n": ".", "k": "+", "j": "*", "o": "/"}

def run(loggers, write_fn):
    """Run the interactive form. write_fn(request_dict) -> list of result lines. Returns result lines (or None if cancelled)."""
    import curses
    os.environ.setdefault("ESCDELAY", "25")
    form = Form(loggers)
    out = {"lines": None}

    def keyname(stdscr):
        c = stdscr.get_wch()
        m = {curses.KEY_UP: "UP", curses.KEY_DOWN: "DOWN", curses.KEY_LEFT: "LEFT", curses.KEY_RIGHT: "RIGHT",
             curses.KEY_BTAB: "BTAB", curses.KEY_BACKSPACE: "BACKSPACE", curses.KEY_ENTER: "ENTER"}
        if isinstance(c, int): return m.get(c, "")
        if c == "\x1b":
            # curses returns a bare ESC for sequences it does not know, e.g. the numeric keypad in
            # application mode (ESC O p..y = 0..9). Look for the rest of the sequence before treating it as Esc.
            stdscr.nodelay(True)
            try:
                nxt = stdscr.get_wch()
                if nxt == "O":
                    third = stdscr.get_wch()
                    return KEYPAD.get(third, "")
                return ""            # some other escape sequence: ignore rather than quit
            except curses.error:
                return "ESC"         # nothing followed: a real Esc press
            finally:
                stdscr.nodelay(False)
        return {"\n": "ENTER", "\r": "ENTER", "\t": "TAB", "\x7f": "BACKSPACE", "\x08": "BACKSPACE"}.get(c, c)

    def main(stdscr):
        curses.curs_set(1); stdscr.keypad(True)
        os.write(1, b"\x1b>")   # numeric keypad mode: keypad digits arrive as plain digits
        has_color = curses.has_colors()
        if has_color:
            curses.start_color(); curses.use_default_colors()
            for i, col in enumerate((curses.COLOR_RED, curses.COLOR_YELLOW, curses.COLOR_GREEN, curses.COLOR_CYAN), 1): curses.init_pair(i, col, -1)
        attr = {"": 0, "head": curses.A_BOLD, "row": 0, "rowsel": curses.A_REVERSE, "sel": curses.A_REVERSE, "dim": curses.A_DIM,
                "err": curses.color_pair(1) | curses.A_BOLD if has_color else curses.A_BOLD,
                "warn": curses.color_pair(2) if has_color else curses.A_BOLD, "ok": curses.color_pair(3) if has_color else 0}
        while True:
            stdscr.erase(); H, W = stdscr.getmaxyx()
            lines, cur = form.render()
            y = 0
            for text, style in lines:
                if style == "cmd": chunks = [text[i:i + W - 1] for i in range(0, len(text), W - 1)] or [""]   # hard wrap: no characters lost
                else: chunks = textwrap.wrap(text, W - 1, subsequent_indent="  ", drop_whitespace=False) or [""]
                for ch in chunks:
                    if y < H - 1:
                        try: stdscr.addstr(y, 0, ch, attr.get({"cmd": "ok"}.get(style, style), 0))
                        except curses.error: pass
                    y += 1
            curses.curs_set(1 if cur else 0)
            if cur:
                try: stdscr.move(cur[0], min(cur[1], W - 1))
                except curses.error: pass
            stdscr.refresh()
            try: k = keyname(stdscr)
            except KeyboardInterrupt: return
            if k == "": continue
            act = form.key(k)
            if act is None: continue
            if act[0] == "quit": return
            if act[0] == "write":
                try: form.result = write_fn(act[1])
                except Exception as e: form.result = [f"WARNING: write failed: {e}"]
                out["lines"] = form.result; form.stage = "done"

    curses.wrapper(main)
    if out["lines"] is None and form.last_command: print("Last command from the form:\n  " + form.last_command)
    return out["lines"]
