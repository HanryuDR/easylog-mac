import usb.core, usb.util, time, sys
from read_config import devices, read_config
EP_OUT, EP_IN = 0x02, 0x82
def download(d, loggertype):
    d.set_configuration(); usb.util.claim_interface(d, 0)
    try:
        d.ctrl_transfer(0x40,0x02,0x0001,0,None); d.ctrl_transfer(0x40,0x02,0x0002,0,None); time.sleep(0.1)
        d.write(EP_OUT, bytes([0x03,0xFF,0xFF]), timeout=2000); time.sleep(0.025)
        hl = 4 if loggertype in (20,26) else 3
        h = bytes(d.read(EP_IN, 64, timeout=3000))
        while len(h) < hl: h += bytes(d.read(EP_IN, 64, timeout=3000))
        n = h[1] | h[2]<<8 | (h[3]<<16 if hl==4 else 0)
        extra = h[hl:]            # data bytes that arrived in the same packet
        buf = bytearray(extra)
        while len(buf) < n:
            buf += bytes(d.read(EP_IN, 64, timeout=3000))
        return h[:hl], bytes(buf[:n])
    finally:
        usb.util.release_interface(d,0); usb.util.dispose_resources(d)
if __name__ == "__main__":
    bus, addr = int(sys.argv[1]), int(sys.argv[2])
    d = usb.core.find(bus=bus, address=addr)
    t = read_config(d)[1][0]
    h, data = download(usb.core.find(bus=bus,address=addr), t)
    print("hdr", h.hex(), "bytes", len(data))
    open(f"data_bus{bus}_addr{addr}.bin","wb").write(data)
    print(data[:32].hex(' '))
