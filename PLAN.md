# EasyLog USB for macOS: findings and plan

## Findings (from decompiled EasyLog USB.exe, observed in source)
- Installer chain: setup.exe (InstallShield, ISSetupStream) -> EasyLog USB.msi -> .NET WinForms
  app "EasyLog USB.exe" (+ EasyLogGraph.exe, ExportToExcel.dll, SiUSBXp.dll).
- "EL-USB Driver Setup.exe" is just the Silicon Labs USBXpress 3.3 driver installer. Nothing else.
- Device: VID 0x10C4, PID 0x0002 (Silabs USBXpress, CP210x-class bridge). Product string contains "easylog".
- USBXpress = raw bulk IN/OUT pipes. SI_Read/SI_Write map to libusb bulk transfers.
  No vendor control requests used by the app. Timeouts: 10 s config, 1 s download.
- Protocol: host writes 3 bytes [cmd, lenLo, lenHi]; device replies.
    cmd 0x00  read config      -> 3-byte header [?, lenLo, lenHi] then len bytes (256B typical)
    cmd 0x04  read big config  -> 1536B (types 64-70: 512 main + 4x256 channel blocks)
    cmd 0x01  write config     -> header carries ConfigSize, then config bytes, then poll-read 1 byte until 0xFF
    cmd 0x03  download data    -> header (3 or 4 bytes; 4 for types 20/26 = 24-bit length), then data in 512-byte packets
    cmd 0x10  read config (post-stop/final download variant, 4096B buffer)
  Sleep 25 ms between write and read; flush RX/TX before each command.
- Config block (offsets, little endian), type = byte[0]:
    [0] logger type, [2..17] name (ASCII), [18..23] start time H/M/S/D/M/Y(2-digit) (BCD on types 64-70),
    [24..27] span/offset, [28..29] sample period s (types 64-70: /8), [30..31] samples stored,
    [32..33] flag bits (bit 8 = running, bit 9 = download pending; bit 0 = degF), [47] flags2,
    [48..51] firmware ASCII, [52..55] serial u32, [58] session count, [60..61] max samples,
    [260..265] current clock set by host (types other than 64-70), [267] session sample count.
  Types: 1/2 EL-USB-1, 3 EL-USB-2, 4/6 -3, 5/7 -4, 8 LITE, 9 CO, 10 TC, 11 CO300, 12 -2-LCD, 13 -2+,
  14 -1-PRO, 15 TC-LCD, 16 -2-LCD+, 17 -5, 18 -1-RCG, 19/21 -1-LCD, 20 OEM-3, 22 TC, 23 TC-LCD,
  26 ACT, 27 TP-LCD, 64-70 = newer multichannel (EL-USB-5 family etc).
- Data decode: 8-bit types (1,2): degC = 0.5*raw - 40 (degF = raw - 40). 16-bit types: big-endian
  u16 raw, then per-type scale/offset + user calibration (m*x + c). Timestamps = start + i*period.
  Rollover mode reorders samples (start index = nSamples*2+2).
- The Excel macros under "Excel Macro" are just importers of the txt/CSV export.

## Not yet verified (unknowns)
- Exact USB endpoint addresses and interface number (need a real device; run `lsusb -v` equivalent).
- Whether macOS needs a code-signed helper: no kext should claim 10C4:0002, libusb should open it.
- Per-model raw->unit conversion tables (many branches in stop.cs processData ~2,000 lines).
- Alarm, calibration and LCD config offsets (decompiled but not yet tabulated).

## Plan
Phase 0: hardware probe (1 evening). Plug in a logger, dump descriptors with pyusb/libusb,
         confirm endpoints, send cmd 0x00 and capture raw config. Save as fixtures.
Phase 1: Python library `easylog` (pyusb/libusb) - device discovery, read_config, parse header
         for the one model Daniel owns first, download_data, CSV export identical to Windows app.
         Golden tests from fixtures plus decompiled-code behaviour.
Phase 2: Config writing (name, period, start mode, alarms, clock sync) with read-back verify.
         Refuse to write unknown types.
Phase 3: CLI (`easylog info|download|configure|stop`), then SwiftUI app with Swift Charts,
         IOUSBHost or libusb via a thin C shim; sandbox needs com.apple.security.device.usb.
Phase 4: Remaining models, calibration, PDF/CSV export.

Recommendation: Python first (fast to iterate against real hardware), port to Swift once
the byte layout is pinned down. Do NOT port the WinForms UI; rebuild from the config schema.

## Artifacts
- Decompiled C# (local working copy, NOT in the repository): decompiled-csharp/ (76k lines, ilspycmd)
- ISSetupStream extractor (local, NOT in the repository): isx.py
- Extracted MSI payload (local, NOT in the repository): msi_payload/

## Hardware probe results (EL-USB-1, 2026-10-21) - OBSERVED
- macOS enumerates it as "USB API" 10c4:0002, no driver claims it; pyusb/libusb claims interface 0 fine.
- Endpoints: bulk OUT 0x02, bulk IN 0x82, 64-byte packets. One interface.
- REQUIRED handshake after claim (USBXpress SI_Open equivalent), else bulk OUT/IN time out:
    ctrl_transfer(0x40, 0x02, 0x0001, 0)  # flush buffers
    ctrl_transfer(0x40, 0x02, 0x0002, 0)  # clear-to-send
  (recalled from USBXpress conventions, confirmed empirically: device answers right after.)
- cmd 00 FF FF -> header 02 40 00 (type 2, 64 bytes) then 64-byte config. Reads are deterministic.
- probe/read_config.py reads and saves config; fixture: probe/config_el-usb-1.bin
- Config looks partly sane (cal floats 1.0 / -40.0 at 0x20-0x2b, serial 127069 at 52-55) but name/start/
  period fields look like noise. Type-2 layout differs from the generic offsets, or logger is unconfigured. TODO.

## USB-502 (type 3) download + decode - OBSERVED 2026-10-21
- cmd 03 FF FF -> header 02 00 80 (0x8000 = 32768 bytes), then 32768 data bytes in 64-byte USB packets. probe/download.py
- Data = interleaved byte pairs [temp, rh] per sample. temp: degF = raw-40 (config byte 46 nonzero; NOT the flags word at 32), degC = raw*0.5-40; rh = raw*0.5.
  Dew point (Magnus) from the decompiled stop.cs. Sample count from config bytes 30-31 (16382). probe/decode.py
- Device currently holds run "Downstairs" 2021-08-15 13:53:45 -> 2021-09-07 07:55:45, 120 s period.
- The Windows files in data saved with windows are DIFFERENT runs (2018-2023), none matches that start time, so no byte-for-byte check yet.
- Dew point recomputed from the Windows files' own T/RH matches within 0.13 F (rounding in Windows' F<->C conversion), not exact.
- Windows exports: .txt and .csv are the same comma format (index,time,T,RH,dew,serial-on-row-1); Downstairs.csv was re-saved by Excel (m/d/yy hh:mm, ints).

## Exporter (phase 1 started) - 2026-10-21
- easylog/ package: `python3 -m easylog list` / `download --index N -o file.csv`. Read-only: _command() asserts cmd in (0x00,0x03).
- Dew point port (ftoc/ctof rounding to 0.1 per decompiled code) matches 72,395 rows of the Windows exports with 0 mismatches.
- Temp unit for type 3 = config byte 46. Type 2 (EL-USB-1) layout unsupported until it reads sanely.
- Outstanding: raw byte->temp not verified against a known Windows file for the 502 (none exists); rollover-mode reordering untested.

## Exporter (phase 1 started) - 2026-10-21
- easylog/ package: `python3 -m easylog list` / `download --index N -o file.csv`. Read-only: _command() asserts cmd in (0x00,0x03).
- Dew point port (ftoc/ctof rounding to 0.1 per decompiled code) matches 72,395 rows of the Windows exports, 0 mismatches.
- Temp unit for type 3 = config byte 46. Type 2 (EL-USB-1) layout unsupported until it reads sanely.
- Outstanding: raw byte->temp not verified against a known Windows file for the 502; rollover-mode reordering untested.

## EL-USB-1 (type 2) - OBSERVED 2026-10-21
- Same USB protocol. Data download cmd 03 returns header 02 00 40 (0x4000=16384 bytes); an empty 0-length packet may precede it.
- Data = one byte/sample, degF = raw-40 (degC = raw*0.5-40). VERIFIED: matches Windows Keggerator.txt (2023-08-15 20:36:54, 10 s, serial 127069)
  for 16381/16382 samples; CSV export reproduces the Windows file byte-for-byte except row 1.
- Row 1: device byte[0] is 0xFF (would be 215F); Windows file has 81.0. Cause unknown (marker/overwritten slot after power loss?). Buffer ends with ff 00 ff.
- Config bytes 2-51 (name/start/period/count/unit) were garbage on first read (cause not established; the logger had been idle since 2023); serial (52-55) is intact. The logger still holds the
  Keggerator run, so name/start/period must be supplied by hand: `python3 -m easylog download --index 1 --name ... --start ... --period 10 --samples 16382 --unit F`.
- Next: config write path (set name/period/clock/start) is needed to make this logger usable again; not implemented, needs care.

## CLI complete for type 1/2 (2026-10-22) - VERIFIED
- `python3 -m easylog list|status|start|stop|download [--index N]`. start/stop are dry-run unless --yes. Writes limited to type 1/2.
- End-to-end CLI run: start(10 s, F) -> 95 s -> stop -> download = exactly 10 samples, 81-82 F, Windows CSV format.
- Logger index order can change between runs; always `list` first.
- Remaining: type 3 (USB-502) write builder + test; SwiftUI app; sensor self-heating check (unplug, compare to 74 F room).

## USB-502 (type 3) fully integrated (2026-10-22) - VERIFIED
- Same write path as type 2, 128-byte block (cmd 01 80 00). build_start()/stop_config() handle types 1,2,3. No clock/BCD needed.
- Live test: start 10 s F -> 95 s -> stop -> download = 10 samples, 74-75 F (thermostat 74 F), RH 42-62% (spike at sample 6 = handling/breath), LEDs flashed per sample.
- EL-USB-1 read 81-82 F in the same room => EL-USB-1 reads ~7 F high (self-heating on USB or sensor offset). To check: unplug, log on a shelf, compare.
- CLI: select with --serial N (preferred; 127069 = EL-USB-1, 10070370 = USB-502). Index order is unstable.

## CLI parameter limits (conservative, 2026-10-22) - TO BE LOOSENED BY TESTING
Defined in easylog/config_build.py (NAME_MAX_LEN, NAME_ALLOWED, PERIOD_MIN_S/MAX_S, START_MAX_AHEAD_S); help text in __main__.py must be updated with them.
- name: 1-16 chars, [A-Za-z0-9 -_] (Windows forbids \\ " % & * , . / : < > ? | ( ); non-ASCII/other punctuation untested)
- period: 10-86400 s (hardware-tested: 10 s, 120 s). To test: minimum (<10 s?), maximum (65535 hardware field), odd values.
- start: now, --delay 0-7 days, or --start local time (future only). To test: longer delays, push-to-start (builder supports it, not exposed).
- start refuses when logger is logging or has unread data unless --overwrite.

## Published specs (Lascar datasheets, fetched 2026-10-22) - what the vendor documents
Sources: lascarelectronics.com EL-USB-1 datasheet iss17 (02/2021) and EL-USB-2 iss16 (02/2021). No Lascar page exists for "USB-502"; type 3 = EL-USB-2 family (temp+RH) by behaviour.
- Logging rate: user selectable 10 s to 12 h (43200 s). Both models. (Hardware period field is 16-bit, so 65535 is the theoretical max.)
- Memory: 16,382 readings (EL-USB-1: temp; EL-USB-2: 16,382 temp + 16,382 RH).
- Resolution 0.5 C (1 F, 0.5 %RH). Immediate and delayed start. Logger name and unit configurable.
- LED codes: green double flash = armed, delayed start pending; green single = logging; green triple (EL-USB-2) / green+amber (EL-USB-1) = memory full, stopped; no LEDs = stopped/no battery. EL-USB-2 alternates temp/RH LEDs every 10 s.
- Not documented anywhere found: name character set (only the 16-byte field), maximum start delay, minimum rate below 10 s.
- Battery: leaving the logger on USB for long periods drains it; RH sensor response ~20 min to 90% of a step change; datasheet accuracy +/-0.45 C typical.

## Name-field limits (hardware-tested 2026-10-22, probe/name_test.py)
- Device accepts and round-trips ANY byte tried: 1 and 16 chars, inner/leading/trailing spaces, all printable ASCII 33-126, Latin-1 (e, degree, mu, u-umlaut, nbsp, y-umlaut). 105/105 on EL-USB-1 and USB-502. Untested: control chars, NUL, 0x7F-0x9F, 17+ chars (builder asserts <=16).
- Real constraints are in the files/apps: comma breaks the unquoted CSV header, '/' ':' break the default <name>.csv file name, and the Windows app forbids \\ " % & * , . / : < > ? | ( ). CLI therefore uses the vendor rule: printable ASCII minus those 14, no leading/trailing space.
- Interval cap lowered to the vendor's 12 h (43200 s). Sub-10 s intentionally not tested (user decision).
- Lesson: probe scripts that call the builder directly bypass the CLI's overwrite guard; they need their own (name_test.py now refuses to run on a logger that is logging / has unread data unless --overwrite). An un-downloaded tail of the EL-USB-1 side-by-side run was lost to this.

## Interactive form (easylog/tui.py)
curses, stdlib only. Form (pure logic, unit-testable) + run() shell. Tested through a pty with pyte (probe/tui_drive.py): navigation, logger switch, validation messages, confirm screen with erase warning, real write on EL-USB-1 (ack True, logging).
Not yet done: download/stop/status screens, pre-fill from the logger's current run, absolute --start time field.
- build.sh: zipapp build + libusb check/brew install + optional --install. Tested: normal, missing libusb with brew, missing without brew, skip flag, bad option.

## Battery and USB (observed 2026-10-22, EL-USB-1 serial 127069)
- No battery, plugged into USB: red LED on, device does NOT enumerate (no Silicon Labs 0x10C4 device on the bus; `easylog -l` says "no logger connected").
- Battery inserted: LEDs flash in a series then go dark (power-on self-test, presumably). On USB with a battery: LEDs dark, device enumerates and reads normally.
- Working interpretation (Daniel's guess, consistent with the above, not in any vendor doc found): steady red on USB without a battery = "insert a battery". Treat the battery as REQUIRED to talk to an EL-USB-1 over USB. USB-502 untested without a battery.
- Earlier claims that the odd config bytes / byte[1]=0xF2 came from battery loss were inference only; the cause is unknown.
- version 1.2026-10-22 (easylog/__init__.py __version__); no-arg shows help; -V/--version.
