"""Drive `easylog interactive` through a pty and print the emulated screen after each step. Needs pyte (scratch install)."""
import sys, os, pty, time, select, fcntl, termios, struct, json
sys.path.insert(0, os.path.expanduser("~/.hermes/cache/scratch/pyte_t"))
import pyte
ROWS, COLS = 30, 100
steps = json.loads(sys.argv[1])
pid, fd = pty.fork()
if pid == 0:
    os.environ["TERM"] = "xterm-256color"; os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    os.execv("/opt/homebrew/bin/python3", ["python3", "-m", "easylog", "interactive"])
fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
screen = pyte.Screen(COLS, ROWS); stream = pyte.ByteStream(screen)
KEYS = {"UP": b"\x1bOA", "DOWN": b"\x1bOB", "RIGHT": b"\x1bOC", "LEFT": b"\x1bOD", "ENTER": b"\r", "ESC": b"\x1b", "TAB": b"\t", "BS": b"\x7f", "KP0": b"\x1bOp", "KP1": b"\x1bOq", "KP2": b"\x1bOr", "KP3": b"\x1bOs", "KP5": b"\x1bOu", "KP9": b"\x1bOy", "KPENTER": b"\x1bOM"}
def pump(t=0.6):
    end = time.time() + t
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            try: d = os.read(fd, 65536)
            except OSError: return False
            if not d: return False
            stream.feed(d)
    return True
def dump(label):
    print(f"=== {label} ==="); print("\n".join(l.rstrip() for l in screen.display).rstrip()); print()
pump(1.5); dump("start")
for st in steps:
    if st.startswith("#"): dump(st[1:]); continue
    for t in st.split(" "):
        if t in KEYS: os.write(fd, KEYS[t]); pump(0.15)
        else: os.write(fd, t.encode()); pump(0.25)
    pump(0.3)
alive = pump(1.0)
try:
    pid_done, status = os.waitpid(pid, os.WNOHANG)
    print("child exited:", pid_done != 0, "status", status)
except ChildProcessError: print("child gone")
