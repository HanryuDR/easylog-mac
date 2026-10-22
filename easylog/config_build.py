"""PURE functions (no USB I/O): build the 64-byte type-1/2 (EL-USB-1) config the Windows app would write.
Ported from loggerFunctions.setDeviceName/setSamplePeriod/setTempUnit/setStartDate/setSpan/setPushStart/setloggingState."""
import datetime as dt

# Conservative limits (tested values only). Loosen after hardware testing (see PLAN.md).
NAME_MAX_LEN = 16                       # hardware field is 16 bytes; Windows app also caps at 16
NAME_FORBIDDEN = '\\"%&*,./:<>?|()'   # the vendor app's own forbidden set (loggerFunctions.checkValidCharacters)
NAME_ALLOWED = "".join(chr(c) for c in range(32, 127) if chr(c) not in NAME_FORBIDDEN)   # printable ASCII; hardware accepts any byte (tested 105 names)
PERIOD_MIN_S, PERIOD_MAX_S = 10, 43200  # vendor spec: 10 s to 12 h. Hardware-tested so far: 10 s, 120 s
START_MAX_AHEAD_S = 7 * 86400           # delayed start up to 7 days ahead

def check_params(name, period_s, delay_s):
    """Return a list of problems (empty = OK)."""
    e = []
    if not 1 <= len(name) <= NAME_MAX_LEN: e.append(f"name must be 1-{NAME_MAX_LEN} characters (got {len(name)})")
    bad = sorted({ch for ch in name if ch not in NAME_ALLOWED})
    if bad: e.append("name has unsupported characters: " + " ".join(repr(b) for b in bad) + "  (allowed: printable ASCII except " + " ".join(NAME_FORBIDDEN) + ")")
    if name != name.strip(): e.append("name must not start or end with a space")
    if not PERIOD_MIN_S <= period_s <= PERIOD_MAX_S: e.append(f"period must be {PERIOD_MIN_S}-{PERIOD_MAX_S} seconds (got {period_s})")
    if delay_s < 0: e.append("start time is in the past")
    if delay_s > START_MAX_AHEAD_S: e.append(f"start time is more than {START_MAX_AHEAD_S // 86400} days ahead")
    return e

def build_start(current: bytes, name: str, period_s: int, fahrenheit: bool,
                      start: dt.datetime, now: dt.datetime, push_start=False) -> bytes:
    assert current[0] in (1, 2, 3) and len(current) == {1: 64, 2: 64, 3: 128}[current[0]]
    assert 1 <= len(name) <= 16 and all(ord(ch) < 256 for ch in name)
    assert 1 <= period_s <= 0xFFFF
    span = int((start - now).total_seconds())
    assert span >= 0, "start time must not be before now"
    c = bytearray(current)
    c[1] = 0                                                          # REQUIRED: stale nonzero byte[1] makes the logger ignore the start
    c[2:18] = name.encode('latin-1').ljust(16, b'\0')                 # name, NUL padded
    c[18], c[19], c[20] = start.hour, start.minute, start.second      # plain binary, not BCD
    c[21], c[22], c[23] = start.day, start.month, start.year % 100
    c[24:28] = span.to_bytes(4, 'little')                             # delay before start, seconds
    c[28:30] = period_s.to_bytes(2, 'little')
    c[30:32] = b'\0\0'                                                # samples stored = 0
    c[33] |= 0x01                                                     # word@32 bit 8: logging ON
    c[46] = 1 if fahrenheit else 0                                    # whole byte is the unit for type 1/2
    c[47] = (c[47] | 0x80) if push_start else (c[47] & ~0x80)         # bit 7 push-to-start
    return bytes(c)

def stop_config(current: bytes) -> bytes:
    c = bytearray(current); c[33] &= ~0x01; c[24:28] = b'\0\0\0\0'; return bytes(c)   # stopLogger()+clearOffset()

build_type2_start = build_start; stop_type2 = stop_config   # old names
