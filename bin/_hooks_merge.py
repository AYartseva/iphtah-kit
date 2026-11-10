""
import json
import os
import shutil
import sys
import time


def runnable(command):
    ""
    words = (command or "").split()
    if not words:
        return False
    path = os.path.expanduser(words[0])
    return os.path.isfile(path) and os.access(path, os.X_OK)


def widen_matcher(want_entry, have_entries, event, out):
    ""
    if not isinstance(want_entry.get("matcher"), str):
        return 0
    keys = {(h.get("command"), h.get("if")) for h in want_entry.get("hooks", []) if isinstance(h, dict)}
    changed = 0
    for t in have_entries:
        if not isinstance(t, dict) or not isinstance(t.get("hooks"), list):
            continue
        if t.get("matcher") in (None, "", "*") or not isinstance(t.get("matcher"), str):
            continue
        have_alts = t["matcher"].split("|")
        missing = [a for a in want_entry["matcher"].split("|") if a and a not in have_alts]
        if not missing:
            continue
        if not any(isinstance(h, dict) and (h.get("command"), h.get("if")) in keys for h in t["hooks"]):
            continue
        new = "|".join(have_alts + missing)
        out(f"hook matcher: {event} {[h.get('command') for h in t['hooks'] if isinstance(h, dict)][:1]} "
            f"{t['matcher']!r} -> {new!r}")
        t["matcher"] = new
        changed += 1
    return changed


def merge(want, retired, d, out=print, can_run=runnable):
    ""
    have = d.setdefault("hooks", {})
    if not isinstance(have, dict):
        out("hooks: the settings' « hooks » is not an object; left alone")
        return 1
    diffs = 0
    for event, entries in list(have.items()):
        if not isinstance(entries, list):
            continue
        kept = []
        for e in entries:
            if not isinstance(e, dict) or not isinstance(e.get("hooks"), list):
                kept.append(e)
                continue
            hooks = []
            for h in e["hooks"]:
                cmd = h.get("command") if isinstance(h, dict) else None
                if cmd in retired:
                    diffs += 1
                    if can_run(retired[cmd]):
                        out(f"hook retired: {event} {cmd}")
                        continue
                    out(f"hook kept, successor missing: {event} {cmd} (needs {retired[cmd].split()[0]})")
                hooks.append(h)
            if hooks:
                kept.append(dict(e, hooks=hooks))
            elif not e["hooks"]:
                kept.append(e)
        have[event] = kept
    for event, entries in want.items():
        if event in have and not isinstance(have[event], list):
            diffs += 1
            out(f"hook: {event} left alone: the settings hold something other than a list there")
            continue
        cmds = {(h.get("command"), h.get("if")) for e in have.get(event, []) if isinstance(e, dict)
                for h in (e.get("hooks") if isinstance(e.get("hooks"), list) else []) if isinstance(h, dict)}
        for e in entries:
            diffs += widen_matcher(e, have.get(event, []), event, out)
            new = [h for h in e.get("hooks", []) if (h.get("command"), h.get("if")) not in cmds]
            if new:
                diffs += 1
                out(f"hook: {event} {[h.get('command') + (' if ' + h['if'] if h.get('if') else '') for h in new]}")
                have.setdefault(event, []).append(dict(e, hooks=new))
    return diffs


def main(argv):
    src, dst, check = argv[0], os.path.realpath(argv[1]), argv[2] == "1"
    spec = json.load(open(src))
    d = json.load(open(dst)) if os.path.exists(dst) else {}
    diffs = merge(spec["hooks"], dict(spec.get("retired", {})), d)
    if diffs and not check:
        if os.path.exists(dst):
            keep = f"{dst}.before-hooks-merge-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
            shutil.copyfile(dst, keep + ".tmp"); os.replace(keep + ".tmp", keep)
            print(f"hooks backup (the undo of this run): {keep}")
        with open(dst + ".tmp", "w") as fh:
            json.dump(d, fh, indent=2)
        os.replace(dst + ".tmp", dst)
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
