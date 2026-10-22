import usb.core, usb.util, time, sys
EP_OUT, EP_IN = 0x02, 0x82
def devices(): return list(usb.core.find(find_all=True, idVendor=0x10c4, idProduct=0x0002))
def read_config(d, cmd=0x00):
    d.set_configuration(); usb.util.claim_interface(d, 0)
    try:
        d.ctrl_transfer(0x40,0x02,0x0001,0,None); d.ctrl_transfer(0x40,0x02,0x0002,0,None)
        time.sleep(0.1)
        d.write(EP_OUT, bytes([cmd,0xFF,0xFF])); time.sleep(0.025)
        def rn(n):
            b=bytearray()
            while len(b)<n: b+=bytes(d.read(EP_IN,64,timeout=3000))
            return bytes(b)
        h=rn(3); n=h[1]|h[2]<<8; time.sleep(0.025)
        return h, rn(n)
    finally:
        usb.util.release_interface(d,0); usb.util.dispose_resources(d)
if __name__=="__main__":
    for d in devices():
        h,c=read_config(d)
        tag=f"bus{d.bus}_addr{d.address}"
        open(f"config_{tag}.bin","wb").write(c)
        print("==",tag,"hdr",h.hex(),len(c),"bytes")
        for i in range(0,len(c),16): print(f"{i:04x}",c[i:i+16].hex(' '))
