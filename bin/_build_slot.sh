take_build_slot() {
  local state=$1 lock=$2 slots=${3:-1} got= i waited=
  if ! command -v flock >/dev/null 2>&1; then
    echo "this repository's builds take a lock (« lock » in its client file), which needs flock: not found." >&2
    echo "  Install it (Linux: util-linux; macOS: brew install flock), or remove « lock » from the client file." >&2
    exit 2
  fi
  mkdir -p "$state"
  while [ -z "$got" ]; do
    for i in $(seq 1 "$slots"); do
      exec 9>"$state/$lock.$i.lock"
      if flock -n 9; then got=$i; break; fi
      exec 9>&-
    done
    if [ -z "$got" ]; then
      [ -n "$waited" ] || echo "waiting: $slots $lock build(s) already running on this machine…"
      waited=1; sleep "${IPHTAH_LOCK_WAIT:-15}"
    fi
  done
}
