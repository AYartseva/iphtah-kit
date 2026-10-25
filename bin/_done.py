""
import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def _is_kit(root):
    ""
    if os.path.basename(root) == "iphtah-kit" and os.path.basename(os.path.dirname(root)) == ".claude":
        return True
    try:
        with open(os.path.join(root, "VERSION")) as f:
            return f.readline().startswith("method ")
    except OSError:
        return False


IN_KIT = _is_kit(ROOT) or _is_kit(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DONE = os.path.join(ROOT, "done.json") if IN_KIT else None
FLOOR = "merge-check"
RECORDS = "done-records"
NAME = re.compile(r"[A-Za-z0-9][\w.-]*\Z")
EXAMPLE_WHY = "your reason, in a sentence of your own"
WHY_WORDS = 3


UNSPACED = re.compile(r"[\u0e00-\u0e7f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
WHY_LETTERS = 6


def _words(text):
    return re.findall(r"[^\W_]+", text.lower())


def placeholder(why):
    ""
    words = _words(why)
    if words == _words(EXAMPLE_WHY):
        return True
    if len(set(words)) >= WHY_WORDS:
        return False
    return len(set(UNSPACED.findall(why))) < WHY_LETTERS


def one_printable_line(why):
    ""
    return not any((unicodedata.category(ch)[0] == "C" and ch != "\u200d") or unicodedata.category(ch) in ("Zl", "Zp")
                   for ch in why)


class DoneError(ValueError):
    pass


def _read(path):
    ""
    if path is None or not os.path.exists(path):
        return [], {}
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise DoneError(f"{path} cannot be read ({type(e).__name__}): fix it, or remove it to keep only the "
                        f"{FLOOR} floor")
    checks = data.get("checks") if isinstance(data, dict) else None
    if not isinstance(checks, list):
        raise DoneError(f"{path} has no « checks » list")
    out, seen = [], set()
    for i, c in enumerate(checks):
        if not isinstance(c, dict) or not isinstance(c.get("name"), str) or not NAME.match(c["name"]):
            raise DoneError(f"{path}: check {i + 1} has no one-word « name »")
        if c["name"] in seen:
            raise DoneError(f"{path}: the check « {c['name']} » is listed twice")
        seen.add(c["name"])
        repos = c.get("repos")
        if repos is not None and not (isinstance(repos, list) and all(isinstance(r, str) for r in repos)):
            raise DoneError(f"{path}: check « {c['name']} »: « repos » must be a list of repository names")
        if c["name"] == FLOOR:
            continue
        if not isinstance(c.get("run"), str) or not c["run"].strip():
            raise DoneError(f"{path}: check « {c['name']} » has no « run » command")
        out.append(c)
    removed = data.get("removed", [])
    if not isinstance(removed, list):
        raise DoneError(f"{path}: « removed » must be a list of {{\"name\": …, \"why\": …}}")
    gone = {}
    for i, r in enumerate(removed):
        if not isinstance(r, dict) or not isinstance(r.get("name"), str) or not NAME.match(r["name"]):
            raise DoneError(f"{path}: removed entry {i + 1} has no one-word « name »")
        name = r["name"]
        if name in gone:
            raise DoneError(f"{path}: « {name} » is removed twice")
        if not isinstance(r.get("why"), str) or not r["why"].strip():
            raise DoneError(f"{path}: the removal of « {name} » has no « why »: write in one line why it goes "
                            f"(the decision, in your words), or put « {name} » back in « checks »")
        if not one_printable_line(r["why"]):
            raise DoneError(f"{path}: the « why » of the removal of « {name} » must be one line of printable text: "
                            f"write it without line breaks or control characters")
        if placeholder(r["why"]):
            raise DoneError(f"{path}: the « why » of the removal of « {name} » is a placeholder: write the reason in "
                            f"a sentence of your own, {WHY_WORDS} words or more, or put « {name} » back in « checks »")
        if name in seen:
            raise DoneError(f"{path}: « {name} » is both in « checks » and in « removed »: keep it in one of them")
        gone[name] = r["why"].strip()
    return out, gone


def load(path=DONE):
    ""
    return _read(path)[0]


def floor_why(path=DONE):
    ""
    return _read(path)[1].get(FLOOR)


def floor_asked(path=DONE):
    ""
    return FLOOR not in _read(path)[1]


def applies(check, repo):
    return check.get("repos") is None or repo in check["repos"]


def recorded(state_dir, repo, sha):
    ""
    path = os.path.join(state_dir, RECORDS)
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return {p[2] for p in (l.split() for l in f) if len(p) >= 3 and p[0] == repo and p[1] == sha}


def missing(state_dir, repo, sha, path=DONE):
    ""
    checks = [c for c in load(path) if applies(c, repo)]
    if not checks:
        return []
    have = recorded(state_dir, repo, sha)
    return [c["name"] for c in checks if c["name"] not in have]
