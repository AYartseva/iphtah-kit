""
import os

PLACEHOLDER = "PURPOSE MISSING: what is it for, what must it stop, what must it never block?"
TEMPLATE = """# Purpose of this lot (the session fills it before the first agent starts)

- What is this code or guard for?
- What does it protect against, and against whom (an accident, or an adversary)?
- What must it NEVER block (the false-positive side)?
"""


def stable_root():
    return os.path.expanduser("~/.local/state/iphtah-kit/scratch")


def valid_lot(lot):
    return bool(lot) and lot not in (".", "..") and os.path.basename(lot) == lot and "\0" not in lot


def lot_dir(lot):
    return os.path.join(stable_root(), lot)


def read_purpose(path, lot):
    if path:
        text = open(path, encoding="utf-8", errors="replace").read().strip()
    else:
        p = os.path.join(lot_dir(lot), "purpose.md") if valid_lot(lot) else None
        try:
            text = open(p, encoding="utf-8", errors="replace").read().strip() if p and os.path.isfile(p) else ""
        except OSError:
            text = ""
    return None if not text or text == TEMPLATE.strip() else text


def ensure_template(lot):
    if not valid_lot(lot):
        return False
    p = os.path.join(lot_dir(lot), "purpose.md")
    try:
        os.makedirs(lot_dir(lot), exist_ok=True)
        with open(p, "x", encoding="utf-8") as f:
            f.write(TEMPLATE)
        return True
    except OSError:
        return False
