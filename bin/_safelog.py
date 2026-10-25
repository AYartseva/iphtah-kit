""
import contextlib
import os
import sys


def log(*args, **kw):
    ""
    run(lambda: __import__("_decisions").record(*args, **kw))


def run(fn, *args):
    ""
    try:
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.flush()
            except Exception:
                pass
        std = []
        for fd in (1, 2):
            try:
                st = os.fstat(fd)
                std.append((st.st_dev, st.st_ino))
            except OSError:
                pass
        try:
            saved = os.dup(1)
        except OSError:
            return
        try:
            null = os.open(os.devnull, os.O_WRONLY | os.O_CLOEXEC)
            try:
                os.dup2(null, 1)
            finally:
                os.close(null)
        except OSError:
            os.close(saved)
            return
        try:
            with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink):
                import _decisions
                _decisions.AVOID = frozenset(std)
                fn(*args)
        finally:
            os.dup2(saved, 1)
            os.close(saved)
    except BaseException:
        pass
