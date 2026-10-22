#!/bin/zsh
# Build dist/easylog, a single executable file (Python zipapp, pyusb bundled).
#
#   ./build.sh              build dist/easylog
#   ./build.sh --install    build, then sudo-copy it to /usr/local/bin/easylog
#   ./build.sh --no-libusb-check   skip the libusb check (for offline builds)
#
# libusb is a runtime requirement of the built tool. If it is missing and Homebrew is
# installed, this script runs `brew install libusb`; without Homebrew it tells you what to do.
set -eu
cd "${0:A:h}"

INSTALL=0; CHECK=1
for a in "$@"; do
  case "$a" in
    --install) INSTALL=1 ;;
    --no-libusb-check) CHECK=0 ;;
    -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $a (try --help)" >&2; exit 2 ;;
  esac
done

# --- Python
command -v python3 >/dev/null || { echo "python3 not found on PATH" >&2; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' || { echo "need Python 3.9 or newer (found $(python3 -V))" >&2; exit 1; }

# --- libusb (found the same way pyusb finds it)
have_libusb() {
  python3 - <<'PY'
import ctypes.util, os, sys
found = ctypes.util.find_library("usb-1.0") or any(os.path.exists(p + "/libusb-1.0.dylib") for p in ("/opt/homebrew/lib", "/usr/local/lib"))
sys.exit(0 if found else 1)
PY
}
if (( CHECK )); then
  if have_libusb; then
    echo "libusb: found"
  elif command -v brew >/dev/null; then
    echo "libusb: not found; Homebrew detected, running: brew install libusb"
    brew install libusb
    have_libusb || { echo "libusb still not found after brew install" >&2; exit 1; }
    echo "libusb: installed"
  else
    echo "libusb: NOT FOUND and Homebrew is not installed." >&2
    echo "  Install Homebrew (https://brew.sh) then run: brew install libusb" >&2
    echo "  (or re-run with --no-libusb-check to build anyway; the tool will not find loggers without it)" >&2
    exit 1
  fi
fi

# --- build
STAGE=$(mktemp -d "${TMPDIR:-/tmp}/easylog-build.XXXXXX")
trap 'rm -rf "$STAGE"' EXIT
cp -R easylog "$STAGE/easylog"
find "$STAGE" -name __pycache__ -type d -prune -exec rm -rf {} +
printf 'import runpy\nrunpy.run_module("easylog", run_name="__main__", alter_sys=True)\n' > "$STAGE/__main__.py"
mkdir -p dist
python3 -m zipapp "$STAGE" -o dist/easylog -p "/usr/bin/env python3"
chmod +x dist/easylog
echo "built: $PWD/dist/easylog ($(wc -c < dist/easylog | tr -d ' ') bytes)"
./dist/easylog help | sed -n 3p >/dev/null && echo "smoke test: ok"

# --- install
if (( INSTALL )); then
  echo "installing to /usr/local/bin/easylog (sudo may ask for your password)"
  sudo install -m 755 dist/easylog /usr/local/bin/easylog
  echo "installed: $(command -v easylog || echo /usr/local/bin/easylog)"
fi
