import math, datetime as dt
def decode_type3(cfg, data, fahrenheit=None):
    u=lambda a,b:int.from_bytes(cfg[a:b],'little')
    flags=u(32,34); f = bool(flags & 1) if fahrenheit is None else fahrenheit
    n=u(30,32); period=u(28,30)
    start=dt.datetime(2000+cfg[23],cfg[22],cfg[21],cfg[18],cfg[19],cfg[20])
    name=cfg[2:18].split(b'\0')[0].decode('latin-1'); serial=u(52,56)
    rows=[]
    for i in range(n):
        t=data[2*i]-40.0 if f else data[2*i]*0.5-40.0
        rh=data[2*i+1]*0.5
        tc=(t-32)*5/9 if f else t
        g=0.66077+7.5*tc/(237.3+tc)+math.log10(rh)-2.0 if rh>0 else float('nan')
        dc=(0.66077-g)*237.3/(g-8.16077)
        dp=dc*9/5+32 if f else dc
        rows.append((i+1,start+dt.timedelta(seconds=i*period),t,rh,dp))
    return name,serial,f,rows
