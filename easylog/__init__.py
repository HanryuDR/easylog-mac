"""Read Lascar EasyLog EL-USB-2 / USB-502 style loggers (type 3/12/13/16) on macOS via libusb."""
__version__ = "1.2026-10-22"   # format: major.YYYY-MM-DD of the last change; bump on each release
import math, time, datetime as dt
import os, sys
try:
    import usb.core, usb.util          # a system-installed pyusb wins if present
except ModuleNotFoundError:            # otherwise use the bundled pure-Python copy (needs: brew install libusb)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "_vendor"))
    import usb.core, usb.util

VID, PID, EP_OUT, EP_IN = 0x10C4, 0x0002, 0x02, 0x82

def find_loggers():
    return list(usb.core.find(find_all=True, idVendor=VID, idProduct=PID))

class Logger:
    def __init__(self, dev): self.dev = dev
    def __enter__(self):
        d = self.dev
        d.set_configuration(); usb.util.claim_interface(d, 0)
        d.ctrl_transfer(0x40, 0x02, 0x0001, 0, None)   # flush
        d.ctrl_transfer(0x40, 0x02, 0x0002, 0, None)   # clear to send
        time.sleep(0.1); return self
    def __exit__(self, *a):
        usb.util.release_interface(self.dev, 0); usb.util.dispose_resources(self.dev)
    def _read(self, n, timeout=3000):
        buf = bytearray()
        while len(buf) < n: buf += bytes(self.dev.read(EP_IN, 64, timeout=timeout))
        return bytes(buf)
    def _command(self, cmd):          # read-only commands only (0x00 config, 0x03 data)
        assert cmd in (0x00, 0x03), "write commands are deliberately not implemented"
        self.dev.write(EP_OUT, bytes([cmd, 0xFF, 0xFF]), timeout=2000); time.sleep(0.025)
        first = bytes(self.dev.read(EP_IN, 64, timeout=3000))
        while len(first) < 3: first += bytes(self.dev.read(EP_IN, 64, timeout=3000))
        n = first[1] | first[2] << 8; body = first[3:]
        if len(body) < n: body += self._read(n - len(body))
        return first[0], body[:n]
    def write_config(self, block, timeout_s=5.0):
        """EXPERIMENTAL. Windows sequence: 01 lo hi, 25ms, block, 25ms, poll 1 byte until 0xFF (with a timeout here)."""
        n = len(block); assert n in (64, 128), "unsupported config size"
        try:
            while True: self.dev.read(EP_IN, 64, timeout=100)      # drain stale input
        except usb.core.USBTimeoutError: pass
        self.dev.write(EP_OUT, bytes([0x01, n & 0xFF, n >> 8]), timeout=10000); time.sleep(0.025)
        self.dev.write(EP_OUT, bytes(block), timeout=10000); time.sleep(0.025)
        end = time.time() + timeout_s; got = []
        while time.time() < end:
            try: r = bytes(self.dev.read(EP_IN, 64, timeout=500))
            except usb.core.USBTimeoutError: continue
            got += list(r)
            if 0xFF in r: return True, bytes(got)
        return False, bytes(got)
    def config(self): return self._command(0x00)[1]
    def data(self):   return self._command(0x03)[1]

def parse_config(c):
    u = lambda a, b: int.from_bytes(c[a:b], 'little')
    return dict(type=c[0], name=c[2:18].split(b'\0')[0].decode('latin-1'),
        start=dt.datetime(2000 + c[23], c[22], c[21], c[18], c[19], c[20]),
        period=u(28, 30), samples=u(30, 32), fahrenheit=c[46] != 0,
        firmware=c[48:53].decode('latin-1'), serial=u(52, 56))

def _r1(x): return round(x + 0.0, 1)
def ftoc(f): return _r1((f - 32.0) * 0.5555555556)
def ctof(c): return _r1(1.8 * c + 32.0)
def dewpoint(t, rh, fahrenheit):
    """Port of EasyLog's Magnus formula incl. its intermediate rounding."""
    tc = ftoc(t) if fahrenheit else t
    g = 0.66077 + 7.5 * tc / (237.3 + tc) + math.log10(rh) - 2.0
    d = (0.66077 - g) * 237.3 / (g - 8.16077)
    return ctof(d) if fahrenheit else d

def export_csv(cfg, data, path):
    """Write Windows-EasyLog-compatible CSV (type 3 family), CRLF line endings."""
    f = cfg['fahrenheit']; unit = "Fahrenheit(°F)" if f else "Celsius(°C)"
    with open(path, 'w', encoding='latin-1', newline='') as out:
        out.write(f"{cfg['name']},Time,{unit},Humidity(%rh),Dew Point({'°F' if f else '°C'}),Serial Number\r\n")
        for i in range(cfg['samples']):
            t = data[2*i] - 40.0 if f else data[2*i] * 0.5 - 40.0
            rh = data[2*i+1] * 0.5
            ts = cfg['start'] + dt.timedelta(seconds=i * cfg['period'])
            row = f"{i+1},{ts:%Y-%m-%d %H:%M:%S},{t:.1f},{rh:.1f},{dewpoint(t, rh, f):.1f}"
            if i == 0: row += f",{cfg['serial']:09d}"
            out.write(row + "\r\n")


def export_csv_type12(cfg, data, path):
    """EL-USB-1 / type 1,2: one byte per sample. cfg needs name,start,period,samples,fahrenheit,serial.
    Windows format: index,time,temp,serial-on-row-1."""
    f = cfg['fahrenheit']; unit = "Fahrenheit(°F)" if f else "Celsius(°C)"
    with open(path, 'w', encoding='latin-1', newline='') as out:
        out.write(f"{cfg['name']},Time,{unit},Serial Number\r\n")
        for i in range(cfg['samples']):
            t = data[i] - 40.0 if f else data[i] * 0.5 - 40.0
            ts = cfg['start'] + dt.timedelta(seconds=i * cfg['period'])
            row = f"{i+1},{ts:%Y-%m-%d %H:%M:%S},{t:.1f}"
            if i == 0: row += f",{cfg['serial']:09d}"
            out.write(row + "\r\n")
