""
import json
import os
import re
import stat
import sys
import time

MAX_CODE = 48
MAX_BYTES = 1_000_000
MAX_STATE = 4096
AVOID = None
_WRITE = os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
_READ = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC
_BAD = re.compile(r"[^A-Za-z0-9_.:=<>%-]+")
_DIGITS = re.compile(r"\d")
_RUN = re.compile(r"\d{5,}")


def code(value):
    ""
    text = str(value)
    if "/" in text or "@" in text or _RUN.search(text) or len(_DIGITS.findall(text)) >= 7:
        return "redacted"
    return _BAD.sub("_", text)[:MAX_CODE].strip("_") or "?"


def log_path():
    ""
    p = os.environ.get("IPHTAH_DECISIONS_LOG")
    if p:
        return p
    if "unittest" in sys.modules:
        return None
    return os.path.expanduser("~/.local/state/iphtah-kit/decisions.jsonl")


def _avoid():
    ""
    if AVOID is not None:
        return AVOID
    out = set()
    for fd in (1, 2):
        try:
            st = os.fstat(fd)
            out.add((st.st_dev, st.st_ino))
        except OSError:
            pass
    return frozenset(out)


def _ours(st):
    ""
    return stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and (st.st_dev, st.st_ino) not in _avoid()


def _regular(fd):
    return _ours(os.fstat(fd))


def _open(path, flags, mode=0o600):
    ""
    try:
        fd = os.open(path, flags, mode)
    except OSError:
        return None
    try:
        if _regular(fd):
            return fd
    except OSError:
        pass
    os.close(fd)
    return None


def _read_small(path):
    ""
    fd = _open(path, _READ)
    if fd is None:
        return None
    try:
        return os.read(fd, MAX_STATE).decode("utf-8", "replace")
    except OSError:
        return None
    finally:
        os.close(fd)


def _same_as_last(p, state_key, key):
    ""
    try:
        return json.loads(_read_small(p + ".last") or "").get(state_key) == key
    except (ValueError, AttributeError, TypeError):
        return False


def _remember(p, state_key, key):
    try:
        try:
            state = json.loads(_read_small(p + ".last") or "")
        except ValueError:
            state = {}
        if not isinstance(state, dict):
            state = {}
        state[state_key] = key
        tmp = f"{p}.last.{os.getpid()}.tmp"
        try:
            os.unlink(tmp)
        except OSError:
            pass
        fd = _open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
        if fd is None:
            return
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        os.replace(tmp, p + ".last")
    except Exception:
        pass


def _rotate(p, fd, st):
    ""
    try:
        import fcntl
        lock = _open(p + ".lock", os.O_WRONLY | os.O_CREAT | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
        if lock is None:
            return fd
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return fd
            try:
                same = os.stat(p).st_ino == st.st_ino
            except FileNotFoundError:
                same = False
            if same:
                os.replace(p, p + ".1")
            new = _open(p, _WRITE)
            if new is None:
                return fd
            os.close(fd)
            return new
        finally:
            os.close(lock)
    except OSError:
        return fd


def record(decider, kind, signals, winner, rule, wait_s=0, by="tool", state_key=None):
    ""
    try:
        p = log_path()
        if p is None:
            return False
        entry = {"decider": code(decider), "kind": code(kind), "signals": [code(s) for s in list(signals)[:2]],
                 "winner": code(winner), "rule": code(rule)}
        key = None
        if state_key is not None:
            key = json.dumps(entry, sort_keys=True)
            if _same_as_last(p, code(state_key), key):
                return False
        line = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **entry,
                           "wait_s": max(0, int(wait_s)), "by": "session" if by == "session" else "tool"},
                          ensure_ascii=True, separators=(",", ":")) + "\n"
        try:
            fd = os.open(p, _WRITE, 0o600)
        except FileNotFoundError:
            os.makedirs(os.path.dirname(p), mode=0o700, exist_ok=True)
            fd = os.open(p, _WRITE, 0o600)
        try:
            st = os.fstat(fd)
            if not _ours(st):
                return False
            if st.st_size > MAX_BYTES:
                fd = _rotate(p, fd, st)
            os.write(fd, line.encode("ascii"))
        finally:
            os.close(fd)
        if key is not None:
            _remember(p, code(state_key), key)
        return True
    except Exception:
        return False


def read(path=None):
    ""
    out, bad = [], 0
    base = path or log_path()
    if not base:
        return out, bad
    for f in (base + ".1", base):
        fd = _open(f, _READ)
        if fd is None:
            continue
        try:
            with os.fdopen(fd, encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    if not raw.strip():
                        continue
                    try:
                        d = json.loads(raw)
                        if not isinstance(d, dict):
                            raise ValueError
                        out.append(d)
                    except ValueError:
                        bad += 1
        except OSError:
            pass
    return out, bad
