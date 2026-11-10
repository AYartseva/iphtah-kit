#!/usr/bin/env python3
"""install.py — put this kit into your Claude Code, safely; take it out again, whole.

    python3 install.py [--role lead-dev|dev] [--agent claude|codex] [--dry-run] [--yes] [--home DIR]
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

--agent codex (the default is claude) puts the same kit into Codex CLI instead of Claude Code, with the same care: steps 1,
4 and 5 are the same (the kit's folder is shared by both agents); step 2 appends the marked block to ~/.codex/AGENTS.md (Codex
has no @import, so the kit's texts are written into the block; what you wrote stays before it) and step 3 merges the role's
hooks into ~/.codex/hooks.json, each run through a small shim (bin/_codex_hooks.py), with the role's shell rules as one more
gate. One difference you should know: Codex lets a command through when a hook itself fails or times out (Claude Code blocks
it), so on Codex the gates guard against accidents, not against an adversary. Codex also runs a hook only once it is trusted,
and skips an untrusted one without a word: the installer prints the one command that trusts the kit's hooks (and no other).
Run the installer for each agent you use; --uninstall takes the kit out of both.

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
import subprocess
import sys
import importlib.util

HERE = os.path.dirname(os.path.realpath(__file__))
KIT = ".claude/iphtah-kit"
KIT_STATE = ".local/state/iphtah-kit"
BACKUPS = ".claude/iphtah-kit-backup"
ROLES = ("lead-dev", "dev")
AGENTS = ("claude", "codex")
# The Codex path: the files the publish made per role (codex/<role>.*); the constants below mirror the publish's, which a test holds equal.
CODEX_DIR = ".codex"
DENY_FILE = "codex-deny.json"                 # in the kit's folder: the rules of the role's deny gate
AGENTS_WORKS_FOR = "@@works-for.md@@"         # where the person's own works-for.md goes in codex/<role>.agents.md
CODEX_DOC_LIMIT = 32 * 1024                   # Codex's own default project_doc_max_bytes: what it reads of instruction files
CODEX_DOC_BUDGET = 29 * 1024                  # what the kit's block may take of it
# A build command that builds nothing: merge-check would go GREEN on it and push-gate would then let any push through.
NOOP_BUILDS = {"", "true", ":", "/bin/true", "/usr/bin/true", "exit 0"}
NO_BUILD = ("needs its full build command (build=COMMAND, run from the repository's root): without one, or with a "
            "no-op such as « true », merge-check would record a green build having built nothing")
REPO_ONLY = {"README.md", "CONTRIBUTING.md", "install.py", "install.sh"}   # this repository's, not the kit's
THEIRS = ("done.json", "works-for.md")                                      # written once, never replaced
STAMP, WHATS_NEW, DONE_DEFAULT = "VERSION", "WHATS-NEW.md", "done.default.json"
# A user timer, every 5 minutes: `egress sample` records what this account's processes talk to, on this machine only,
# so a Claude left alone has a record of its normal traffic to read with `egress profile`.
EGRESS_UNITS = {
    "iphtah-kit-egress.service": """[Unit]
Description=Iphtah kit: egress sample, what this account's processes talk to

[Service]
Type=oneshot
Nice=19
TimeoutStartSec=60
ExecStart=%h/{kit}/bin/egress sample
""",
    "iphtah-kit-egress.timer": """[Unit]
Description=Iphtah kit: every 5 minutes, one snapshot of outgoing connections

[Timer]
OnCalendar=*-*-* *:00/5:20

[Install]
WantedBy=timers.target
""",
}
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

def repo_only(rel, codex):
    """True for a file of this repository that the kit's folder does not take: its own README, CONTRIBUTING and installer, and
    the Codex path's install sources (codex/, the hooks merge, the note agents-codex.md: AGENTS.md holds the note). The Codex
    shim goes into the folder only for a home that runs the kit on Codex, so a Claude install is exactly what it was."""
    return rel in REPO_ONLY or rel == "agents-codex.md" or rel.startswith("codex/") or rel == "bin/_hooks_merge.py" \
        or (rel == "bin/_codex_hooks.py" and not codex)


def kit_plan(home, src, role, deny=None, codex=False):
    """{home path: text or None (remove)} for the kit folder, and the files that are theirs and stay. The home's
    VERSION lists only what was installed, plus the role. `deny` (Codex only): the text of codex-deny.json, the rules of
    the role's deny gate, written into the folder and listed in VERSION so an update or an uninstall knows it."""
    root = os.path.join(home, KIT)
    want = {}
    for rel in stamp_files(read(os.path.join(src, STAMP))):
        if repo_only(rel, codex) or not inside(src, rel):
            continue
        text = read(os.path.join(src, rel))
        if text is not None:
            want[rel] = text
    if deny is not None:
        want[DENY_FILE] = deny
    want[STAMP] = "".join(l + "\n" for l in (read(os.path.join(src, STAMP)) or "").splitlines()
                          if not l.startswith(("file ", "role ")) or l[len("file "):] in want) \
        + (f"file {DENY_FILE}\n" if deny is not None else "") + f"role {role}\n"
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

def load_settings(path, by_hand="merge the role's settings by hand from roles/settings/"):
    text = read(path)
    if text is None:
        return {}, None, 2
    try:
        d = json.loads(text)
    except ValueError as e:
        sys.exit(f"install.py: {path} is not plain JSON ({e}); it is left as it is and nothing is written. Make it "
                 f"plain JSON (no comments, no trailing commas) and run again, or {by_hand}.")
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


def tools_of(matcher):
    """The tools a hook entry's matcher names; None for every tool (no matcher, "" or "*"). An installed hook
    counts as present for an entry only when it covers the entry's tools, so Monitor added to a hook that is already
    installed for Bash is added on an update, not skipped because the command is there."""
    return None if matcher in (None, "", "*") else set(str(matcher).split("|"))


def installed_for(entry, have):
    """True when an installed entry already runs a command of `entry` for all the tools `entry` names."""
    want = tools_of(entry.get("matcher"))
    for e in have:
        if not isinstance(e, dict) or not isinstance(e.get("hooks"), list):
            continue
        got = tools_of(e.get("matcher"))
        if got is None or (want is not None and want <= got):
            if any(isinstance(h, dict) and h.get("command") in {x.get("command") for x in entry.get("hooks", [])}
                   for h in e["hooks"]):
                return True
    return False


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
        for entry in entries:
            if not installed_for(entry, have):
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


# --- the Codex path: ~/.codex/AGENTS.md (one block) and ~/.codex/hooks.json (the kit's hooks) --------------------------
# The files come from the publish, made by the same code as `onboard --agent codex` (codex/<role>.*): this installer only
# merges them, as it merges Claude's. Its own shim (bin/_codex_hooks.py) and the method's hooks merge (bin/_hooks_merge.py)
# are loaded from this clone, never from the person's PATH.

def load_module(path, name):
    """A module of this clone's bin/, loaded without leaving a __pycache__ in the clone."""
    if not os.path.isfile(path):
        return None
    old, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec = importlib.util.spec_from_file_location(name, path)   # not load_module(): Python removes it in 3.15
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = old


def codex_modules(home=None):
    """(the shim, the hooks merge) from this clone's bin/, else (the shim only) the home's kit; None for what is not found."""
    roots = [os.path.join(HERE, "bin")] + ([os.path.join(home, KIT, "bin")] if home else [])
    shim = next((m for m in (load_module(os.path.join(r, "_codex_hooks.py"), "_codex_hooks") for r in roots) if m), None)
    return shim, load_module(os.path.join(HERE, "bin", "_hooks_merge.py"), "_hooks_merge")


def codex_shim_in(home):
    """True when the home's Codex hooks.json calls the kit's shim."""
    return "/_codex_hooks.py run " in (read(os.path.join(home, CODEX_DIR, "hooks.json")) or "")


def codex_files(src, role):
    """(hooks, notes, AGENTS.md template, deny file text) the publish made for `role`; exits when this clone has none."""
    texts = [read(os.path.join(src, "codex", f"{role}.{ext}")) for ext in ("hooks.json", "agents.md", "deny.json")]
    if None in texts or not all(os.path.isfile(os.path.join(src, "bin", f)) for f in ("_codex_hooks.py", "_hooks_merge.py")):
        sys.exit(f"install.py: this kit has no Codex files for {role} (codex/{role}.*, bin/_codex_hooks.py, bin/_hooks_merge.py): "
                 "pull the repository again, or install with --agent claude")
    spec = json.loads(texts[0])
    return spec["hooks"], spec.get("notes", []), texts[1], texts[2]


def codex_block(template, works_for, old_md):
    """The block for ~/.codex/AGENTS.md: the template with the person's own works-for.md written in. Codex reads instruction
    files up to CODEX_DOC_LIMIT bytes and drops the rest silently; the kit's block comes last, so a block that does not fit
    would be the part lost: refused, nothing written."""
    if template.count(AGENTS_WORKS_FOR) != 1:
        sys.exit("install.py: the kit's AGENTS.md text does not hold its works-for.md marker once: pull the repository again")
    body = template.replace(AGENTS_WORKS_FOR, works_for.strip(), 1)
    block = BLOCK_START + "\n" + body.rstrip("\n") + "\n" + BLOCK_END + "\n"
    new = with_block(old_md, block)
    if len(block.encode("utf-8")) > CODEX_DOC_BUDGET or len(new.encode("utf-8")) > CODEX_DOC_LIMIT:
        sys.exit(f"install.py: ~/{CODEX_DIR}/AGENTS.md would be {len(new.encode('utf-8'))} bytes (the kit's block "
                 f"{len(block.encode('utf-8'))}), over what Codex reads of an instruction file ({CODEX_DOC_LIMIT}, "
                 f"project_doc_max_bytes) or the {CODEX_DOC_BUDGET} the kit may take: Codex would drop the end silently. "
                 "Shorten works-for.md or your own AGENTS.md, then run again; nothing written")
    return new


def merge_codex_hooks(current, hooks, shim, merge):
    """`current` (a hooks.json) with the kit's `hooks` it lacks, and a hook of an earlier mapping of the same command retired:
    the merge `onboard --agent codex` makes, by the same code."""
    d = json.loads(json.dumps(current))
    merge.merge(hooks, shim.stale_hooks(hooks, d), d, out=lambda *_: None, can_run=lambda _c: True)
    return d


def unmerge_codex_hooks(current, shim):
    """`current` without the hooks the kit wrote (shim.is_kit_command: its shim, from the kit's bin/, running a tool of the
    kit's; the person's own hooks, even one that borrows the shim's name, stay). An event or `hooks` that this empties goes."""
    if not isinstance(current, dict):   # valid JSON that is not an object ([], 3): not ours, left exactly as it is
        return current
    out = json.loads(json.dumps(current))
    hooks = out.get("hooks")
    if shim is None or not isinstance(hooks, dict):
        return out
    removed = False
    for event in list(hooks):
        entries = hooks[event]
        if not isinstance(entries, list):
            continue
        kept = []
        for e in entries:
            hs = e.get("hooks") if isinstance(e, dict) else None
            left = [h for h in hs if not (isinstance(h, dict) and shim.is_kit_command(h.get("command")))] \
                if isinstance(hs, list) else None
            if left is None or len(left) == len(hs):
                kept.append(e)
                continue
            removed = True
            if left:
                kept.append(dict(e, hooks=left))
        if kept:
            hooks[event] = kept
        elif entries:
            hooks.pop(event)
    if removed and not hooks:
        out.pop("hooks")
    return out


# --- the client file ---------------------------------------------------------------------------------------------

OPTIONS = ("github", "base", "build", "protected")


def parse_repo(spec):
    """`NAME=PATH[,github=OWNER/REPO][,base=BRANCH][,build=COMMAND][,protected=A+B]`. A build= command may contain commas
    (`mvn -pl core,web verify`, `-Dtest=A,B`); only a later `github=`, `base=`, `build=` or `protected=` ends it. For a
    command that itself holds one of those four, use --client-file."""
    name, _, rest = spec.partition("=")
    if not name or not rest:
        sys.exit(f"install.py: --repo wants NAME=PATH[,github=OWNER/REPO][,base=BRANCH][,build=COMMAND]: {spec!r}")
    parts = rest.split(",")
    repo = {"path": parts[0], "base": "main"}
    last = None   # the key whose value the last piece belongs to
    for part in parts[1:]:
        k, _, v = part.partition("=")
        # A build command is free text and may hold commas (`mvn -pl core,web verify`, `-Dtest=A,B`): after a build=, a piece
        # that does not start with a known key and « = » is the rest of that command, comma included (an outside
        # user's report, 06/11/2026). Only a build continues: any other key with a stray piece, or a piece before
        # any key, still says « unknown key », so a mistyped option is named instead of swallowed into a path or a branch.
        if last == "build" and not (k in OPTIONS and "=" in part):
            repo["build"] += "," + part
            continue
        if k not in OPTIONS:
            sys.exit(f"install.py: --repo {name}: unknown key {k!r} (github, base, build, protected)")
        repo[k] = v.split("+") if k == "protected" else v
        last = k
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
    codex = a.agent == "codex"
    names = ("AGENTS.md", "hooks.json") if codex else ("CLAUDE.md", "settings.json")
    md_path = os.path.join(home, CODEX_DIR if codex else ".claude", names[0])
    st_path = os.path.join(home, CODEX_DIR if codex else ".claude", names[1])
    writable_or_die(md_path)
    writable_or_die(st_path)
    old_md = read(md_path)
    deny, notes = None, []
    if codex:
        hooks, notes, template, deny = codex_files(src, a.role)
        shim, merge = codex_modules()
        works_for = read(os.path.join(home, KIT, "works-for.md"))
        if works_for is None:
            works_for = read(os.path.join(src, "works-for.md")) or ""
        new_md = codex_block(template, works_for, old_md or "")
        old_obj, old_st, indent = load_settings(st_path, "merge the kit's hooks by hand from codex/*.hooks.json")
        new_obj, added = merge_codex_hooks(old_obj, hooks, shim, merge), {"deny": [], "hooks": [], "created": []}
    else:
        new_md = with_block(old_md, block_text(src, a.role, a.context))
        old_obj, old_st, indent = load_settings(st_path)
        role_settings = read(os.path.join(src, "roles", "settings", f"{a.role}.settings.json"))
        if role_settings is None:
            sys.exit(f"install.py: {src}/roles/settings/{a.role}.settings.json is missing: this kit has no settings for {a.role}")
        new_obj, added = merge_settings(old_obj, json.loads(role_settings))
        if codex_shim_in(home):   # the home also runs the kit on Codex: its deny gate follows the role, and fails closed without its file
            deny = read(os.path.join(src, "codex", f"{a.role}.deny.json"))
    new_st = old_st if new_obj == old_obj and old_st is not None else dump_settings(new_obj, indent, old_st)
    kit, kept = kit_plan(home, src, a.role, deny, codex or codex_shim_in(home))
    clients = os.path.join(home, KIT, "clients")
    existing = [f for f in (os.listdir(clients) if os.path.isdir(clients) else [])
                if os.path.isfile(os.path.join(clients, f, "project.json"))]
    cf = client_file(a, home, existing)
    if cf:
        kit[cf[0]] = cf[1]
    return dict(md_path=md_path, old_md=old_md, new_md=new_md, st_path=st_path, old_st=old_st, new_st=new_st,
                added=added, kit=kit, kept=kept, client=cf, existing=existing, names=names, notes=notes)


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
    for path, text in p["egress"].items():
        if read(path) != text:
            changes += 1
            print(f"{'+' if read(path) is None else '~'} {path} (a user timer, every 5 minutes: what this account's processes talk to, kept on this machine only, in {os.path.join(home, KIT_STATE, 'egress.jsonl')}; started with systemctl --user enable --now iphtah-kit-egress.timer)")
    for note in p["notes"]:
        print(f"! not on Codex: {note}")
    if p["client"] is None:
        if p["existing"]:
            print(f"= client file kept: {', '.join(p['existing'])} (yours)")
        else:
            print("! no client file: the kit's push-gate and merge-check then know no repository. Add one with "
                  "--client NAME --login LOGIN --repo NAME=PATH[,github=OWNER/REPO][,base=main][,build=CMD], or "
                  "--client-file PATH, any time.")
    return changes


def egress_units(home, src):
    """{path: text} of the timer's units, or {} when this kit copy has no egress tool."""
    if not os.path.isfile(os.path.join(src, "bin", "egress")) or not shutil.which("systemctl"):
        return {}   # a Mac or a container: no timer that could never run; `egress sample` still runs by hand
    return {os.path.join(home, ".config/systemd/user", name): text.format(kit=KIT) for name, text in EGRESS_UNITS.items()}


def systemctl_user(home, *args):
    """Only for the real home: a --home install (a test, a copy) writes the units and touches no running systemd."""
    if (os.path.realpath(home) != os.path.realpath(os.path.expanduser("~")) or not shutil.which("systemctl")
            or os.environ.get("IPHTAH_KIT_NO_SYSTEMD")):
        return None
    try:
        return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None


def enable_egress_timer(home):
    r = systemctl_user(home, "daemon-reload")
    r = r and systemctl_user(home, "enable", "--now", "iphtah-kit-egress.timer")
    if r is not None and r and r.returncode == 0:
        print("egress timer on: `egress profile` shows what this account talks to. It runs while you are logged in, "
              "unless you run: loginctl enable-linger")
    else:
        print("! egress timer not started (no user session here?). The units are written; run: "
              "systemctl --user enable --now iphtah-kit-egress.timer")


def backup(home, p, role, agent="claude"):
    folder = os.path.join(home, BACKUPS, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    n = 0
    while os.path.exists(folder + (f"-{n}" if n else "")):
        n += 1
    folder += f"-{n}" if n else ""
    os.makedirs(folder)
    manifest = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "role": role, "files": {}}
    for name, path, old, new in ((p["names"][0], p["md_path"], p["old_md"], p["new_md"]),
                                 (p["names"][1], p["st_path"], p["old_st"], p["new_st"])):
        if old is not None:
            shutil.copy2(path, os.path.join(folder, name))
        manifest["files"][name] = {"existed": old is not None, "after": sha(new) if old != new else None}
    manifest["added"] = p["added"]
    if agent != "claude":
        manifest["agent"] = agent
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
    if a.agent == "codex" and a.context:
        sys.exit("install.py: --context is an @import line, which Codex lacks: Codex reads the project's own AGENTS.md from "
                 "the client's repository. Leave --context out with --agent codex")
    p = plan_install(a, home, src)
    p["egress"] = egress_units(home, src)
    changes = show_install(p, home)
    if a.dry_run:
        print("\n(dry run: nothing written)")
        return 0
    if not changes:
        print("\nNothing to do: the kit is installed as it is in this repository.")
        return 0
    if a.agent == "codex" and not shutil.which("python3"):   # every hook of the kit runs through python3; Codex lets a call through when its hook fails
        sys.exit("install.py: python3 is not on the PATH, and every Codex hook of the kit runs through it. Codex does NOT stop a "
                 "call whose hook failed, so the gates would silently be off. Install python3 (macOS: xcode-select --install), "
                 "then run again; nothing written")
    if not a.yes:
        if not sys.stdin.isatty():
            print("\nNothing written: add --yes to install what is listed above (the person's yes).")
            return 2
        if ask("\nInstall this? [y/N]").lower() not in ("y", "yes"):
            print("Nothing written.")
            return 0
    folder = None
    if p["old_md"] != p["new_md"] or p["old_st"] != p["new_st"]:
        folder = backup(home, p, a.role, a.agent)
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
    if any(read(path) != text for path, text in p["egress"].items()):
        for path, text in p["egress"].items():
            write_text(path, text)
        enable_egress_timer(home)
    print("\nwritten." + (f" Your {p['names'][0]} and {p['names'][1]} as they were: {folder}" if folder else ""))
    if a.agent == "codex":
        print("Codex runs these hooks only once they are trusted, and skips an untrusted one without a word. Trust them (the "
              f"kit's, no other) with:\n  CODEX_HOME={os.path.join(home, CODEX_DIR)} python3 "
              f"{os.path.join(home, KIT, 'bin', '_codex_hooks.py')} trust\n"
              "and check with `... status`. Run both again after each update. Edit works-for.md as you wish, then run this "
              "installer again to copy it into AGENTS.md.")
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
    """What leaves: the kit's files, and the kit's part of CLAUDE.md and settings.json (and of Codex's AGENTS.md and hooks.json,
    where the kit was installed with --agent codex). Once that part is out, a
    backup copy that holds exactly what is left is restored byte for byte (their formatting back; a copy taken at
    an update holds an earlier kit, so it never matches); a file that did not exist before the first install and
    holds nothing else is removed; otherwise the file is rewritten without the kit's part, the rest untouched."""
    saved = backups(home)
    added = {"deny": [], "hooks": [], "created": []}   # everything any install added or created, every role
    for _, m in saved:
        for k in added:
            added[k] += [x for x in m.get("added", {}).get(k, []) if x not in added[k]]
    absent_before = {name for _, m in saved for name, info in m.get("files", {}).items() if not info.get("existed")}
    touched = {name for _, m in saved for name in m.get("files", {})}   # the files an install of the kit ever changed
    out = {}   # path: text or None (remove)
    shim = codex_modules(home)[0]
    for name, folder_name in (("CLAUDE.md", ".claude"), ("settings.json", ".claude"), ("AGENTS.md", CODEX_DIR),
                              ("hooks.json", CODEX_DIR)):
        path = os.path.join(home, folder_name, name)
        now = read(path)
        if now is None:
            continue
        if folder_name == ".claude":
            writable_or_die(path)
        if name in ("CLAUDE.md", "AGENTS.md"):
            new, new_obj, empty = without_block(now), None, not without_block(now).strip()
        else:
            try:
                d = json.loads(now)
            except ValueError:
                if folder_name == ".claude" or name in touched:   # a Codex file the kit never touched is not ours to talk about
                    print(f"! {path} is not plain JSON: left as it is (the kit's entries, if any, are yours to remove)")
                continue
            new_obj = unmerge_settings(d, added) if name == "settings.json" else unmerge_codex_hooks(d, shim)
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
        if path in out and folder_name != ".claude":   # Codex's files are checked only when the kit changes them
            writable_or_die(path)
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
    units = [os.path.join(home, ".config/systemd/user", n) for n in EGRESS_UNITS]
    units = [u for u in units if os.path.isfile(u)]
    for u in units:
        plan[u] = None
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
        print(f"= {os.path.join(home, KIT_STATE)} (the kit's records, left where they are: the build results and egress.jsonl, egress.jsonl.1, the reverse-name cache; delete the folder if you want nothing left)")
    if not plan:
        print("Nothing of the kit found.")
        return 0
    if a.dry_run:
        print("\n(dry run: nothing written)")
        return 0
    if units:
        systemctl_user(home, "disable", "--now", "iphtah-kit-egress.timer")
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
    if units:
        systemctl_user(home, "daemon-reload")
        for d in (".config/systemd/user", ".config/systemd", ".config"):
            d = os.path.join(home, d)
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
    print("\nremoved." + (f" The backups stay in {os.path.dirname(folder)}" if folder else ""))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--role", choices=ROLES, help=f"default: the role already installed, else {ROLES[0]}")
    p.add_argument("--agent", choices=AGENTS, default="claude",
                   help="the agent to install the kit into: claude (the default: ~/.claude/CLAUDE.md and settings.json) or "
                        "codex (~/.codex/AGENTS.md and hooks.json; Codex lets a command through when a hook itself fails or "
                        "times out, where Claude Code blocks it). --uninstall takes the kit out of both")
    p.add_argument("--dry-run", action="store_true", help="print the diff, write nothing")
    p.add_argument("--yes", action="store_true", help="the person's yes, when no terminal can ask for it")
    p.add_argument("--uninstall", action="store_true")
    p.add_argument("--home", help="the home to install into (default: yours)")
    p.add_argument("--client", help="the client's name, one word")
    p.add_argument("--login", help="your GitHub login, written as the client file's « author »")
    p.add_argument("--repo", action="append", default=[], metavar="NAME=PATH[,github=OWNER/REPO][,base=B][,build=CMD]",
                   help="a repository the kit's tools build and gate. CMD may contain commas (`mvn -pl core,web verify`); only a "
                        "later github=, base=, build= or protected= ends it (a command holding one of those: use --client-file)")
    p.add_argument("--client-file", help="an existing project.json to install as the client file")
    p.add_argument("--context", help="your client's own context file: one @import line for it is added")
    a = p.parse_args(argv)
    home = os.path.realpath(os.path.expanduser(a.home or "~"))
    if a.context:
        a.context = os.path.abspath(os.path.expanduser(a.context))
        if not os.path.isfile(a.context):
            sys.exit(f"install.py: --context {a.context}: no such file")
    if a.uninstall:
        if a.agent != "claude":
            p.error("--uninstall takes the kit out of both agents: leave --agent out")
        return do_uninstall(a, home)
    return do_install(a, home, HERE)


if __name__ == "__main__":
    sys.exit(main())
