""
import re

SHEBANG_BYTES = 256
PY_SHEBANG = re.compile(rb"^#!.*\bpython")


def is_python_script(first_bytes):
    ""
    return PY_SHEBANG.match(first_bytes[:SHEBANG_BYTES]) is not None
