# EL-USB-1 / type 1-2 write protocol (from decompiled EasyLog USB.exe) - NOT YET TESTED ON HARDWARE

## Wire sequence (DeviceDataFunctions.saveConfig, lines 241-330)
 1. SI_Open; timeouts 10 s read / 10 s write.      -> our: claim iface + the two vendor ctrl requests (flush, clear-to-send)
 2. SI_FlushBuffers(1,1)
 3. bulk OUT:  01 <size lo> <size hi>              (type 1/2: 01 40 00 ; type 3: 01 80 00)
 4. sleep 25 ms
 5. bulk OUT:  the full config block (64 bytes for type 1/2, as read, with edits applied)
 6. sleep 25 ms
 7. bulk IN, 1 byte at a time, loop until the byte == 0xFF (ack).  The decompiled loop has no retry cap; we MUST add a timeout.
 8. SI_Close.
 Windows reads the config first (cmd 00), edits fields in memory, writes the whole block back. Unknown bytes round-trip unchanged.

## Fields touched, type 1/2 (setter -> byte offsets)
 name            setDeviceName     [2..17] latin-1, NUL padded, 1-16 chars (checkValidCharacters restricts charset; not yet read)
 start time      setStartDate      [18]=hour [19]=min [20]=sec [21]=day [22]=month [23]=year%100   (plain binary; BCD only on types 64-70)
 start delay     setSpan           [24..27] u32 LE = seconds from "now" until start (0 = immediate). Windows computes startDate-PC clock.
 period          setSamplePeriod   [28..29] u16 LE seconds
 samples stored  setloggingState   [30..31] zeroed on start
 logging on      setloggingState   word@[32..33] bit 8  == byte[33] bit 0  set on start; stopLogger clears it
 unit            setTempUnit       byte[46] = 1 F / 0 C   (whole byte, type 1/2 only)
 push-to-start   setPushStart      byte[47] bit 7 (LCD loggers only: isLcd && start mode 2)
 logger running  getloggerState    byte[47] bit 4 (read side)
 warnings        getDeviceWarnings word@[32..33] bits 8-12: 8 logging, 9 unread data, 10-12 alarm/ low-battery family (not decoded)
 stop            stopLogger+clearOffset: word@32 bit 8 cleared, span [24..27] = 0   (then saveConfig)
 untouched       [0]=type [1]=? [34..45] cal floats (m=1.0 @36, c=-40.0 @40) [48..51] firmware [52..55] serial [56..63]

 Start-time validity: Windows refuses a start earlier than PC clock -1 s. There is no separate "set clock" for type 1/2:
 the logger clock starts from the start time written. (setCurrentDate offsets 260-266 exist only in the >=256-byte configs.)
 A start dialog writes: setStartDate, setPushStart(false unless LCD), setSpan, setloggingState(true), then saveConfig. Name/period/unit come
 from the earlier setup page (setDeviceName, setTempUnit, setSamplePeriod).

## Offline builder
 easylog/config_build.py (pure, no USB). Dry run against the EL-USB-1's current config changes only offsets
 2-24, 28-31, 33, 46. Calibration floats, firmware and serial (52-55) are preserved.

## Risks / unknowns
 - Byte [1] and bytes 56-63 meaning unknown; preserved. Byte 47 other bits preserved.
 - Ack byte semantic: only "0xFF means done" is known; what the device does on a bad block is unknown.
 - Starting a run does NOT erase old data per the code, but the old Keggerator run in the logger is lost once new samples overwrite it:
   DOWNLOAD IT FIRST (we have probe/data_el-usb-1.bin, already saved).
 - type 2 samples: 16384 byte memory, 1 B/sample -> max ~16382 samples.

## VERIFIED ON HARDWARE (EL-USB-1, serial 127069) 2026-10-22
- Write sequence works as documented: 01 40 00, 25 ms, 64-byte block, 25 ms, poll -> ack byte 0xFF. Round-trip write of unchanged config reads back identical.
- Name, start time, period, unit are stored as written. The DEVICE owns bytes 24-27 (span), 30-31 (count), 32-33 (flags):
  it ignores what we write there, except the logging bit is honored only when the start is accepted.
- Start was IGNORED (flags read back 0200, count stale) while byte[1] held 0xF2 (stale value of unknown origin). Writing byte[1]=0
  made the very next write start the run: flags 0203 (bit 8 logging + bit 9 unread data), count 1, then +1 per 10 s.
  => start-block builder must set byte[1]=0 (Windows does this too in getSessionConfig, lines ~2420).
- It logs while plugged into USB (no unplug needed); unplugging is just the Windows UX.
- Stop = clear byte33 bit0 (and span) and write; flags -> 0202, count freezes.
- Test run: 13 samples, 10 s period, 81-82 F while the room was ~74 F (sensor warmed by USB-port/Mac; the 2023 Windows run also started at 81-82).
  First data byte is now valid (0x79), so the 0xFF in slot 0 of the old run was a stale leftover.
