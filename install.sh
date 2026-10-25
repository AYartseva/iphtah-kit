#!/bin/sh
# install.sh — runs install.py with this machine's python3 (the kit's tools are Python too, so it is needed anyway).
# POSIX sh, macOS and Linux. Every option goes through to install.py: --dry-run, --uninstall, --role, --help …
here=$(cd "$(dirname "$0")" && pwd) || exit 1
if command -v python3 >/dev/null 2>&1; then
    exec python3 "$here/install.py" "$@"
fi
echo "install.sh: python3 was not found; the kit's tools need it. Install it, then run again." >&2
exit 1
