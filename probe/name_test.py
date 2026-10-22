"""Name-field limits test. Writes each candidate name (immediate start, 10 s, F), reads the config back, compares.
Bypasses the CLI name limits on purpose (calls build_start directly). Usage: python3 probe/name_test.py SERIAL"""
import sys, os, json, datetime as dt, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from easylog import find_loggers, Logger, parse_config
from easylog.config_build import build_start, stop_config

serial = int(sys.argv[1]); results = []
cands = [("1 char", "A"), ("16 chars", "ABCDEFGHIJKLMNOP"), ("space inside", "A B"), ("trailing space", "AB "), ("leading space", " AB")]
cands += [(f"ASCII {c!r}", f"A{chr(c)}B") for c in range(33, 127)]
cands += [(f"Latin-1 {chr(c)!r}", f"A{chr(c)}B") for c in (0xE9, 0xB0, 0xB5, 0xFC, 0xA0, 0xFF)]
for label, name in cands:
    pass
dev = None
for d in find_loggers():
    with Logger(d) as l:
        if int.from_bytes(l.config()[52:56], 'little') == serial: dev = d
if dev is None: sys.exit("serial not found")
with Logger(dev) as l:
    c0 = l.config()
    if (c0[33] & 3) and "--overwrite" not in sys.argv:
        sys.exit("logger is logging or has unread data: download it first (easylog download ...) or pass --overwrite")
    for label, name in cands:
        cur = l.config(); now = dt.datetime.now().replace(microsecond=0)
        try: blk = build_start(cur, name, 10, True, now, now)
        except AssertionError as e: results.append((label, name, "BUILD-REJECTED", str(e))); continue
        ok, _ = l.write_config(blk); time.sleep(0.05); rb = l.config()
        got = rb[2:18].split(b'\0')[0].decode('latin-1')
        results.append((label, name, "ack" if ok else "NO-ACK", "OK" if got == name else f"MISMATCH got {got!r}", bool(rb[33] & 1)))
    l.write_config(stop_config(l.config()))
bad = [r for r in results if r[2] != "ack" or not str(r[3]).startswith("OK") or (len(r) > 4 and not r[4])]
print(f"{len(results)} names tried on serial {serial}; {len(results) - len(bad)} round-tripped cleanly and started logging")
for r in bad: print("  PROBLEM:", r)
json.dump(results, open(os.path.join(os.path.dirname(__file__), f"name_test_{serial}.json"), "w"), indent=1)
