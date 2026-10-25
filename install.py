#!/usr/bin/env python3
"""install.py — put this kit into your Claude Code, safely; take it out again, whole.

    python3 install.py [--role lead-dev|dev] [--dry-run] [--yes] [--home DIR]
                       [--client NAME --login LOGIN --repo NAME=PATH[,github=OWNER/REPO][,base=main][,build=CMD]]…
                       [--client-file PATH] [--context PATH]
    python3 install.py --uninstall [--dry-run] [--home DIR]

What it does, in this order, and nothing else:
  1. copies the kit (the files listed in VERSION, less this repository's own README, CONTRIBUTING and installer)
     into ~/.claude/iphtah-kit/; your done.json and works-for.md are written once, from the kit's defaults, and
     never replaced;
  2. appends one marked block to ~/.claude/CLAUDE.md with the @import lines of the kit (what you wrote stays, before
     it and untouched; a later run only refreshes that block);
  3. merges the role's hooks and deny rules into ~/.claude/settings.json: ADDS what is missing, never removes or
     reorders what is there (your indentation is kept);
  4. writes the client file the kit's tools read, ~/.claude/iphtah-kit/clients/<client>/project.json, with your
     GitHub login as "author" (the tools use it to tell your own pull requests from others'), from --client-file or
     from --client, --login and --repo (asked for at the prompt when the terminal is interactive). Each repository
     needs its full build command: with none (or a no-op such as `true`), merge-check would record a green build
     having built nothing, so the installer refuses it;
  5. creates the kit's state folder, ~/.local/state/iphtah-kit/ (mode 700), where the build check keeps its records:
     the green builds push-gate reads, the build results, and the throwaway worktrees it builds in.

Before the first write that changes CLAUDE.md or settings.json, both are copied, as they are, to
~/.claude/iphtah-kit-backup/<timestamp>/ with a manifest of what the run added. A second run changes nothing.
--dry-run prints the diff and writes nothing. --uninstall removes the kit's files, takes the block and the added
entries out again (byte for byte from the backup when nothing else changed since), and leaves your done.json,
works-for.md and the kit's state folder where they are, named.

A settings.json that is not plain JSON (comments, trailing commas) is left alone and named: nothing is written.
Installing is a choice: in a terminal the plan is shown and confirmed first; elsewhere --yes stands for your yes.
"""
import argparse
import datetime
import difflib
import hashlib
import json
import os
import shutil
import stat
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
KIT = ".claude/iphtah-kit"
KIT_STATE = ".local/state/iphtah-kit"
BACKUPS = ".claude/iphtah-kit-backup"
ROLES = ("lead-dev", "dev")
# A build command that builds nothing: merge-check would go GREEN on it and push-gate would then let any push through.
NOOP_BUILDS = {"", "true", ":", "/bin/true", "/usr/bin/true", "exit 0"}
NO_BUILD = ("needs its full build command (build=COMMAND, run from the repository's root): without one, or with a "
            "no-op such as « true », merge-check would record a green build having built nothing")
REPO_ONLY = {"README.md", "CONTRIBUTING.md", "install.py", "install.sh"}   # this repository's, not the kit's
THEIRS = ("done.json", "works-for.md")                                      # written once, never replaced
STAMP, WHATS_NEW, DONE_DEFAULT = "VERSION", "WHATS-NEW.md", "done.default.json"
BLOCK_START = "<!-- iphtah-kit: start (written by install.py; edit outside this block, it is refreshed) -->"
BLOCK_END = "<!-- iphtah-kit: end -->"
CONTEXT_LINE = ("Your client's own context file, kept in the client's repository (how its team works, its rules, its "
                "vocabulary):")


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def read(path):
    return open(path).read() if os.path.isfile(path) else None


def stamp_files(text):
    return [line[len("file "):] for line in (text or "").splitlines() if line.startswith("file ")]


def installed_role(home):
    """The role the kit in this home was installed as (the home's VERSION, else the latest backup's manifest), so a
    second run keeps it: before, a run without --role fell back to lead-dev and gave a dev the wrong block."""
    for line in (read(os.path.join(home, KIT, STAMP)) or "").splitlines():
        if line.startswith("role ") and line[5:].strip() in ROLES:
            return line[5:].strip()
    for _, m in backups(home):
        if m.get("role") in ROLES:
            return m["role"]
    return None


def writable_or_die(path):
    """A file the install would change must be writable where it really lives (a link's target): a read-only one
    is refused before anything is written, never overwritten."""
    target = os.path.realpath(path)
    if os.path.exists(target) and not os.access(target, os.W_OK):
        sys.exit(f"install.py: {path} is read-only ({target}); nothing written. Make it writable and run again.")


def inside(root, rel):
    """True when `rel` stays inside `root` once normalised: a VERSION line names what to copy or remove, and must
    never reach outside the kit folder."""
    if not rel or os.path.isabs(rel) or os.path.normpath(rel).split(os.sep)[0] in ("..", "."):
        return False
    real = os.path.realpath(root)
    return os.path.realpath(os.path.join(real, rel)).startswith(real + os.sep)


# --- the kit's files ------------------------------------------------------------------------------------------

def kit_plan(home, src, role):
    """{home path: text or None (remove)} for the kit folder, and the files that are theirs and stay. The home's
    VERSION lists only what was installed, plus the role."""
    root = os.path.join(home, KIT)
    want = {}
    for rel in stamp_files(read(os.path.join(src, STAMP))):
        if rel in REPO_ONLY or not inside(src, rel):
            continue
        text = read(os.path.join(src, rel))
        if text is not None:
            want[rel] = text
    want[STAMP] = "".join(l + "\n" for l in (read(os.path.join(src, STAMP)) or "").splitlines()
                          if not l.startswith(("file ", "role ")) or l[len("file "):] in want) + f"role {role}\n"
    news = read(os.path.join(src, WHATS_NEW))
    if news is not None:
        want[WHATS_NEW] = news
    kept = []
    for rel, default in (("done.json", DONE_DEFAULT), ("works-for.md", "works-for.md")):
        if os.path.isfile(os.path.join(root, rel)):
            kept.append(rel)
        elif default in want or os.path.isfile(os.path.join(src, default)):
            want[rel] = want.get(default) or read(os.path.join(src, default))
    plan = {os.path.join(root, rel): text for rel, text in want.items()}
    for rel in stamp_files(read(os.path.join(root, STAMP))):
        if rel not in want and inside(root, rel) and os.path.isfile(os.path.join(root, rel)):
            plan[os.path.join(root, rel)] = None
    return plan, kept


# --- CLAUDE.md: one block, appended ---------------------------------------------------------------------------

def block_text(src, role, context):
    body = read(os.path.join(src, "claude-md", role + ".md"))
    if body is None:
        sys.exit(f"install.py: {src}/claude-md/{role}.md is missing: this kit has no CLAUDE.md text for {role}")
    if context:
        body = body.rstrip("\n") + f"\n\n{CONTEXT_LINE}\n\n@{context}\n"
    return BLOCK_START + "\n" + body.rstrip("\n") + "\n" + BLOCK_END + "\n"


def split_block(text):
    """(before, block, after) of a CLAUDE.md; block is None when the file has none."""
    i = text.find(BLOCK_START)
    if i < 0:
        return text, None, ""
    j = text.find(BLOCK_END, i)
    if j < 0:
        sys.exit("install.py: ~/.claude/CLAUDE.md opens the kit's block and never closes it: fix the file by hand")
    j += len(BLOCK_END)
    if text[j:j + 1] == "\n":
        j += 1
    return text[:i], text[i:j], text[j:]


def with_block(old, block):
    before, have, after = split_block(old or "")
    if have is None:
        if not old:
            return block
        return old + ("" if old.endswith("\n") else "\n") + "\n" + block
    return before + block + after


def without_block(text):
    before, have, after = split_block(text)
    if have is None:
        return text
    return (before.rstrip("\n") + "\n" if before.strip() else "") + after


# --- settings.json: add only --------------------------------------------------------------------------------

def load_settings(path):
    text = read(path)
    if text is None:
        return {}, None, 2
    try:
        d = json.loads(text)
    except ValueError as e:
        sys.exit(f"install.py: {path} is not plain JSON ({e}); it is left as it is and nothing is written. Make it "
                 "plain JSON (no comments, no trailing commas) and run again, or merge the role's settings by hand "
                 "from roles/settings/.")
    if not isinstance(d, dict):
        sys.exit(f"install.py: {path} does not hold an object; left as it is, nothing written")
    return d, text, indent_of(text)


def indent_of(text):
    for line in text.splitlines():
        n = len(line) - len(line.lstrip(" \t"))
        if n:
            return "\t" if line[0] == "\t" else n
    return 2


def dump_settings(d, indent, like):
    out = json.dumps(d, indent=indent, ensure_ascii=False)
    return out + ("\n" if not like or like.endswith("\n") else "")


def merge_settings(current, add):
    """`current` with the deny rules and hooks of `add` it lacks, appended; returns (merged, what was added).
    The same merge as the kit developers' onboard tool: deny rules added and never removed, a hook already present
    (same command) not duplicated. A shape it does not know is left alone."""
    out = json.loads(json.dumps(current))
    added = {"deny": [], "hooks": [], "created": []}   # created: the containers this merge made, the only ones an
    deny_add = add.get("permissions", {}).get("deny", [])   # uninstall may take away (an empty list of theirs stays)
    if deny_add:
        if "permissions" not in out:
            added["created"].append("permissions")
        perms = out.setdefault("permissions", {})
        if isinstance(perms, dict) and isinstance(perms.get("deny", []), list):
            if "deny" not in perms:
                added["created"].append("permissions.deny")
            deny = perms.setdefault("deny", [])
            for rule in deny_add:
                if rule not in deny:
                    deny.append(rule)
                    added["deny"].append(rule)
    for event, entries in add.get("hooks", {}).items():
        if "hooks" not in out:
            added["created"].append("hooks")
        hooks = out.setdefault("hooks", {})
        if not isinstance(hooks, dict) or not isinstance(hooks.get(event, []), list):
            continue
        if event not in hooks:
            added["created"].append(f"hooks.{event}")
        have = hooks.setdefault(event, [])
        commands = {h.get("command") for e in have if isinstance(e, dict)
                    for h in (e.get("hooks") if isinstance(e.get("hooks"), list) else []) if isinstance(h, dict)}
        for entry in entries:
            if not any(h.get("command") in commands for h in entry.get("hooks", [])):
                have.append(entry)
                added["hooks"].append([event] + [h.get("command") for h in entry.get("hooks", [])])
    return out, added


def unmerge_settings(current, added):
    """`current` without the deny rules and hook entries a manifest says the install added; the rest untouched. A
    container the install created is taken away once empty; one that was there (their own `"deny": []`, which
    Claude Code itself writes) stays, empty or not."""
    out = json.loads(json.dumps(current))
    created = set(added.get("created", []))
    perms = out.get("permissions")
    if isinstance(perms, dict) and isinstance(perms.get("deny"), list):
        for rule in added.get("deny", []):
            if rule in perms["deny"]:
                perms["deny"].remove(rule)
        if not perms["deny"] and "permissions.deny" in created:
            perms.pop("deny")
        if not perms and "permissions" in created:
            out.pop("permissions")
    for event, *commands in added.get("hooks", []):
        entries = out.get("hooks", {}).get(event) if isinstance(out.get("hooks"), dict) else None
        if not isinstance(entries, list):
            continue
        entries[:] = [e for e in entries if not (isinstance(e, dict) and isinstance(e.get("hooks"), list)
                                                 and [h.get("command") for h in e["hooks"]] == commands)]
        if not entries and f"hooks.{event}" in created:
            out["hooks"].pop(event)
    if isinstance(out.get("hooks"), dict) and not out["hooks"] and "hooks" in created:
        out.pop("hooks")
    return out


# --- the client file ---------------------------------------------------------------------------------------------

def parse_repo(spec):
    name, _, rest = spec.partition("=")
    if not name or not rest:
        sys.exit(f"install.py: --repo wants NAME=PATH[,github=OWNER/REPO][,base=BRANCH][,build=COMMAND]: {spec!r}")
    parts = rest.split(",")
    repo = {"path": parts[0], "base": "main"}
    for part in parts[1:]:
        k, _, v = part.partition("=")
        if k not in ("github", "base", "build", "protected"):
            sys.exit(f"install.py: --repo {name}: unknown key {k!r} (github, base, build, protected)")
        repo[k] = v.split("+") if k == "protected" else v
    repo.setdefault("protected", [repo["base"]])
    if is_noop_build(repo.get("build")):
        sys.exit(f"install.py: --repo {name.strip()} {NO_BUILD}")
    return name.strip(), repo


def is_noop_build(build):
    return not isinstance(build, str) or build.strip() in NOOP_BUILDS


def ask(prompt, default=""):
    got = input(f"{prompt}{' [' + default + ']' if default else ''}: ").strip()
    return got or default


def client_file(a, home, existing):
    """The client file to write: from --client-file, from the flags, from the prompt, or the one already installed
    (None: nothing to write; the kit's gates then check no repository, and say so)."""
    if a.client_file:
        try:
            cfg = json.load(open(os.path.expanduser(a.client_file)))
        except (OSError, ValueError) as e:
            sys.exit(f"install.py: cannot read {a.client_file}: {e}")
        if not isinstance(cfg, dict) or not cfg.get("client"):
            sys.exit(f"install.py: {a.client_file} has no « client » name")
        repos = cfg.get("repos") or {}
        for rname, r in (repos.items() if isinstance(repos, dict) else ()):
            if isinstance(r, dict) and is_noop_build(r.get("build")):
                sys.exit(f"install.py: {a.client_file}: repository {rname} {NO_BUILD}")
    elif a.client or a.repo:
        if not (a.client and a.repo):
            sys.exit("install.py: --client NAME and at least one --repo go together")
        cfg = {"client": a.client, "repos": dict(parse_repo(r) for r in a.repo)}
    elif existing:
        return None
    elif sys.stdin.isatty() and not a.dry_run:
        print("The kit's tools read a client file: which repositories they build and gate. Leave the client name empty "
              "to install the kit without one (you can add it later with --client, --login and --repo).")
        name = ask("client name (one word, used as a folder name)")
        if not name:
            return None
        cfg = {"client": name, "repos": {}}
        while True:
            rname = ask("repository name (empty when done)")
            if not rname:
                break
            path = ask("  local path of its clone")
            github = ask("  GitHub owner/repo (empty if none)")
            base = ask("  base branch", "main")
            build = ask("  full build command, run from the repository's root")
            while is_noop_build(build):
                print(f"  this repository {NO_BUILD}.")
                build = ask("  full build command, run from the repository's root")
            cfg["repos"][rname] = {"path": path, "base": base, "protected": [base], "build": build}
            if github:
                cfg["repos"][rname]["github"] = github
        a.login = a.login or ask("your GitHub login (the tools use it to tell your own pull requests)")
    else:
        return None
    if not cfg.get("author"):
        if not a.login:
            sys.exit("install.py: --login LOGIN (your GitHub login) is needed with the client file: the tools use it as "
                     "« author » to tell your own pull requests from others'")
        cfg["author"] = a.login
    name = cfg["client"]
    if "/" in name or ".." in name or not name.replace("-", "").replace("_", "").replace(".", "").isalnum():
        sys.exit(f"install.py: client name {name!r} must be one folder name (letters, digits, - _ .)")
    cfg["state_dir"] = f"~/{KIT_STATE}/{name}"
    cfg.setdefault("worktrees", f"~/{KIT_STATE}/{name}/worktrees")
    return os.path.join(home, KIT, "clients", name, "project.json"), json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"


# --- plan, show, write ------------------------------------------------------------------------------------------

def diff(path, old, new):
    return "".join(difflib.unified_diff((old or "").splitlines(True), (new or "").splitlines(True),
                                        f"{path} (before)", f"{path} (after)"))


def plan_install(a, home, src):
    md_path = os.path.join(home, ".claude", "CLAUDE.md")
    st_path = os.path.join(home, ".claude", "settings.json")
    writable_or_die(md_path)
    writable_or_die(st_path)
    old_md = read(md_path)
    new_md = with_block(old_md, block_text(src, a.role, a.context))
    old_obj, old_st, indent = load_settings(st_path)
    role_settings = read(os.path.join(src, "roles", "settings", f"{a.role}.settings.json"))
    if role_settings is None:
        sys.exit(f"install.py: {src}/roles/settings/{a.role}.settings.json is missing: this kit has no settings for {a.role}")
    new_obj, added = merge_settings(old_obj, json.loads(role_settings))
    new_st = old_st if new_obj == old_obj and old_st is not None else dump_settings(new_obj, indent, old_st)
    kit, kept = kit_plan(home, src, a.role)
    clients = os.path.join(home, KIT, "clients")
    existing = [f for f in (os.listdir(clients) if os.path.isdir(clients) else [])
                if os.path.isfile(os.path.join(clients, f, "project.json"))]
    cf = client_file(a, home, existing)
    if cf:
        kit[cf[0]] = cf[1]
    return dict(md_path=md_path, old_md=old_md, new_md=new_md, st_path=st_path, old_st=old_st, new_st=new_st,
                added=added, kit=kit, kept=kept, client=cf, existing=existing)


def show_install(p, home):
    changes = 0
    for path, text in sorted(p["kit"].items()):
        old = read(path)
        if text is None:
            print(f"- {path} (no longer in the kit)")
        elif old is None:
            print(f"+ {path}")
        elif old != text:
            print(f"~ {path}")
        else:
            continue
        changes += 1
    for rel in p["kept"]:
        print(f"= {os.path.join(home, KIT, rel)} (yours, kept)")
    state = os.path.join(home, KIT_STATE)
    if not os.path.isdir(state):
        changes += 1
        print(f"+ {state}/ (the kit's state folder, mode 700: the green builds push-gate reads, the build results, the build worktrees)")
    for key, path in (("md", p["md_path"]), ("st", p["st_path"])):
        if p["old_" + key] != p["new_" + key]:
            changes += 1
            print(diff(path, p["old_" + key], p["new_" + key]), end="")
        else:
            print(f"= {path} unchanged")
    if p["client"] is None:
        if p["existing"]:
            print(f"= client file kept: {', '.join(p['existing'])} (yours)")
        else:
            print("! no client file: the kit's push-gate and merge-check then know no repository. Add one with "
                  "--client NAME --login LOGIN --repo NAME=PATH[,github=OWNER/REPO][,base=main][,build=CMD], or "
                  "--client-file PATH, any time.")
    return changes


def backup(home, p, role):
    folder = os.path.join(home, BACKUPS, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    n = 0
    while os.path.exists(folder + (f"-{n}" if n else "")):
        n += 1
    folder += f"-{n}" if n else ""
    os.makedirs(folder)
    manifest = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "role": role, "files": {}}
    for name, path, old, new in (("CLAUDE.md", p["md_path"], p["old_md"], p["new_md"]),
                                 ("settings.json", p["st_path"], p["old_st"], p["new_st"])):
        if old is not None:
            shutil.copy2(path, os.path.join(folder, name))
        manifest["files"][name] = {"existed": old is not None, "after": sha(new) if old != new else None}
    manifest["added"] = p["added"]
    with open(os.path.join(folder, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return folder


def write_text(path, text):
    """Written where the file really lives (a link in a dotfiles setup stays a link, its target gets the text), with
    the mode the file had (a 0600 settings.json stays private), through a temporary file beside it."""
    target = os.path.realpath(path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    mode = stat.S_IMODE(os.stat(target).st_mode) if os.path.exists(target) else None
    with open(target + ".tmp", "w") as f:
        f.write(text)
    if mode is not None:
        os.chmod(target + ".tmp", mode)
    os.replace(target + ".tmp", target)


def do_install(a, home, src):
    a.role = a.role or installed_role(home) or ROLES[0]
    p = plan_install(a, home, src)
    changes = show_install(p, home)
    if a.dry_run:
        print("\n(dry run: nothing written)")
        return 0
    if not changes:
        print("\nNothing to do: the kit is installed as it is in this repository.")
        return 0
    if not a.yes:
        if not sys.stdin.isatty():
            print("\nNothing written: add --yes to install what is listed above (the person's yes).")
            return 2
        if ask("\nInstall this? [y/N]").lower() not in ("y", "yes"):
            print("Nothing written.")
            return 0
    folder = None
    if p["old_md"] != p["new_md"] or p["old_st"] != p["new_st"]:
        folder = backup(home, p, a.role)
    for path, text in sorted(p["kit"].items()):
        if text is None:
            os.remove(path)
        elif read(path) != text:
            write_text(path, text)
        if text is not None and path.startswith(os.path.join(home, KIT, "bin") + os.sep):
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.makedirs(os.path.join(home, KIT_STATE), mode=0o700, exist_ok=True)
    if p["old_md"] != p["new_md"]:
        write_text(p["md_path"], p["new_md"])
    if p["old_st"] != p["new_st"]:
        write_text(p["st_path"], p["new_st"])
    print("\nwritten." + (f" Your CLAUDE.md and settings.json as they were: {folder}" if folder else ""))
    return 0


# --- uninstall ------------------------------------------------------------------------------------------------

def backups(home):
    """Every backup with a manifest, newest first: (folder, manifest)."""
    root = os.path.join(home, BACKUPS)
    out = []
    for name in sorted(os.listdir(root) if os.path.isdir(root) else [], reverse=True):
        m = os.path.join(root, name, "manifest.json")
        if os.path.isfile(m):
            try:
                out.append((os.path.join(root, name), json.load(open(m))))
            except ValueError:
                continue
    return out


def plan_uninstall(home):
    """What leaves: the kit's files, and the kit's part of CLAUDE.md and settings.json. Once that part is out, a
    backup copy that holds exactly what is left is restored byte for byte (their formatting back; a copy taken at
    an update holds an earlier kit, so it never matches); a file that did not exist before the first install and
    holds nothing else is removed; otherwise the file is rewritten without the kit's part, the rest untouched."""
    saved = backups(home)
    added = {"deny": [], "hooks": [], "created": []}   # everything any install added or created, every role
    for _, m in saved:
        for k in added:
            added[k] += [x for x in m.get("added", {}).get(k, []) if x not in added[k]]
    absent_before = {name for _, m in saved for name, info in m.get("files", {}).items() if not info.get("existed")}
    out = {}   # path: text or None (remove)
    for name in ("CLAUDE.md", "settings.json"):
        path = os.path.join(home, ".claude", name)
        now = read(path)
        if now is None:
            continue
        writable_or_die(path)
        if name == "CLAUDE.md":
            new, new_obj, empty = without_block(now), None, not without_block(now).strip()
        else:
            try:
                d = json.loads(now)
            except ValueError:
                print(f"! {path} is not plain JSON: left as it is (the kit's entries, if any, are yours to remove)")
                continue
            new_obj = unmerge_settings(d, added)
            new, empty = (now if new_obj == d else dump_settings(new_obj, indent_of(now), now)), new_obj == {}
        restore = None
        for folder, _ in saved:
            copy = read(os.path.join(folder, name))
            if copy is None:
                continue
            try:
                same = copy == new if new_obj is None else json.loads(copy) == new_obj
            except ValueError:
                same = False
            if same:
                restore = copy
                break
        if restore is not None:
            if restore != now:
                out[path] = restore
        elif empty and name in absent_before:
            out[path] = None
        elif new != now:
            out[path] = new
    folder = saved[0][0] if saved else None
    root = os.path.join(home, KIT)
    for rel in stamp_files(read(os.path.join(root, STAMP))) + [STAMP, WHATS_NEW]:
        path = os.path.join(root, rel)
        if inside(root, rel) and os.path.isfile(path):
            out[path] = None
    return out, folder


def do_uninstall(a, home):
    plan, folder = plan_uninstall(home)
    root = os.path.join(home, KIT)
    for path, text in sorted(plan.items()):
        if text is None:
            print(f"- {path}")
        else:
            print(diff(path, read(path), text), end="")
    theirs = [os.path.join(root, r) for r in THEIRS if os.path.isfile(os.path.join(root, r))]
    clients = os.path.join(root, "clients")
    if os.path.isdir(clients):
        theirs.append(clients)
    for t in theirs:
        print(f"= {t} (yours, left where it is)")
    if os.path.isdir(os.path.join(home, KIT_STATE)):
        print(f"= {os.path.join(home, KIT_STATE)} (the kit's records, left where they are)")
    if not plan:
        print("Nothing of the kit found.")
        return 0
    if a.dry_run:
        print("\n(dry run: nothing written)")
        return 0
    for path, text in sorted(plan.items()):
        if text is None:
            os.remove(path)
        else:
            write_text(path, text)
    for dirpath, dirs, files in os.walk(root, topdown=False):
        if not dirs and not files and dirpath != root:
            os.rmdir(dirpath)
        elif not os.listdir(dirpath):
            os.rmdir(dirpath)
    print("\nremoved." + (f" The backups stay in {os.path.dirname(folder)}" if folder else ""))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--role", choices=ROLES, help=f"default: the role already installed, else {ROLES[0]}")
    p.add_argument("--dry-run", action="store_true", help="print the diff, write nothing")
    p.add_argument("--yes", action="store_true", help="the person's yes, when no terminal can ask for it")
    p.add_argument("--uninstall", action="store_true")
    p.add_argument("--home", help="the home to install into (default: yours)")
    p.add_argument("--client", help="the client's name, one word")
    p.add_argument("--login", help="your GitHub login, written as the client file's « author »")
    p.add_argument("--repo", action="append", default=[], metavar="NAME=PATH[,github=OWNER/REPO][,base=B][,build=CMD]")
    p.add_argument("--client-file", help="an existing project.json to install as the client file")
    p.add_argument("--context", help="your client's own context file: one @import line for it is added")
    a = p.parse_args(argv)
    home = os.path.realpath(os.path.expanduser(a.home or "~"))
    if a.context:
        a.context = os.path.abspath(os.path.expanduser(a.context))
        if not os.path.isfile(a.context):
            sys.exit(f"install.py: --context {a.context}: no such file")
    if a.uninstall:
        return do_uninstall(a, home)
    return do_install(a, home, HERE)


if __name__ == "__main__":
    sys.exit(main())
