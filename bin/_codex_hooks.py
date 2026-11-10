""
import argparse
import json
import os
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

EVENTS = ("PreToolUse", "PostToolUse", "SessionStart", "UserPromptSubmit", "Stop")
PATCH_TOOLS = ("apply_patch", "Edit", "Write")
SHIM = "_codex_hooks.py"
MAX_PAYLOAD = 4 * 1024 * 1024
MAX_CHILD_OUT = 256 * 1024
MAX_ROLLOUT_TAIL = 8 * 1024 * 1024
MAX_COMMAND = 256 * 1024
MAX_FILES = 50

IF_BASH = re.compile(r"Bash\((.*)\)\Z", re.S)



def codex_matcher(matcher):
    ""
    if matcher in (None, "", "*") or not isinstance(matcher, str):
        return matcher, []
    out, dropped = [], []
    for a in (x for x in matcher.split("|") if x):
        if a in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            for t in PATCH_TOOLS:
                if t not in out:
                    out.append(t)
        elif a == "Monitor":
            dropped.append(a)
        elif a not in out:
            out.append(a)
    return ("|".join(out) if out else None), dropped


def shim_command(shim, event, matcher, cond, timeout, command):
    ""
    parts = ["run", "--event", event]
    if isinstance(matcher, str) and matcher not in ("", "*"):
        parts += ["--matcher", matcher]
    if cond:
        parts += ["--if", cond]
    if isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and timeout > 0:
        parts += ["--timeout", str(int(timeout))]
    return " ".join([shim] + [shlex.quote(p) for p in parts]) + " -- " + shlex.quote(command)


def map_hooks(source, shim):
    ""
    out, notes = {}, []
    if not isinstance(source, dict):
        return out, ["hooks: the source is not an object: nothing mapped"]
    for event, entries in source.items():
        if event not in EVENTS:
            notes.append(f"{event}: no verified Codex counterpart in 0.167.0: NOT mapped "
                         f"({_count(entries)} entr{'y' if _count(entries) == 1 else 'ies'})")
            continue
        if not isinstance(entries, list):
            notes.append(f"{event}: not a list in the source: NOT mapped")
            continue
        for e in entries:
            if not isinstance(e, dict) or not isinstance(e.get("hooks"), list):
                notes.append(f"{event}: an entry of an unknown shape: NOT mapped")
                continue
            matcher, dropped = codex_matcher(e.get("matcher"))
            if e.get("matcher") not in (None, "", "*") and matcher is None:
                notes.append(f"{event} {e.get('matcher')!r}: Codex has no such tool ({', '.join(dropped) or 'none left'}): "
                             "NOT mapped")
                continue
            if dropped:
                notes.append(f"{event} {e.get('matcher')!r}: {', '.join(dropped)} dropped from the matcher (Codex has no "
                             f"{dropped[0]} tool); the others stay")
            hooks = []
            for h in e["hooks"]:
                if not isinstance(h, dict) or h.get("type", "command") != "command" or not h.get("command"):
                    notes.append(f"{event}: a hook that is not a command: NOT mapped")
                    continue
                nh = {"type": "command", "command": shim_command(shim, event, e.get("matcher"), h.get("if"),
                                                                   h.get("timeout"), h["command"])}
                for k in ("timeout", "statusMessage"):
                    if k in h:
                        nh[k] = h[k]
                hooks.append(nh)
            if hooks:
                ne = {"hooks": hooks}
                if matcher not in (None, "", "*"):
                    ne = {"matcher": matcher, **ne}
                out.setdefault(event, []).append(ne)
    return out, notes


def _count(x):
    return len(x) if isinstance(x, list) else 1



def if_matches(cond, command):
    ""
    if not cond:
        return True
    m = IF_BASH.match(cond.strip())
    if not m or not isinstance(command, str):
        return True
    body = m.group(1).strip()
    if body.endswith(":*"):
        return re.search(r"(?<![\w.-])" + r"\s+".join(re.escape(w) for w in body[:-2].split()) + r"(?![\w-])", command) is not None
    rx = ".*".join(re.escape(p) for p in body.split("*"))
    return re.fullmatch(rx, command, re.S) is not None


PATCH_FILE = re.compile(r"^\*\*\* (Add|Update|Delete) File: (.+?)\s*$|^\*\*\* Move to: (.+?)\s*$", re.M)


class TooMany(Exception):
    ""


def patch_files(text):
    ""
    out = []
    if not isinstance(text, str) or "*** Begin Patch" not in text:
        return out
    for m in PATCH_FILE.finditer(text):
        if m.group(1):
            out.append(("Write" if m.group(1) == "Add" else "Edit", m.group(2)))
        else:
            out.append(("Edit", m.group(3)))
        if len(out) > MAX_FILES:
            break
    return out


def claude_calls(event, payload, matcher):
    ""
    if event not in ("PreToolUse", "PostToolUse"):
        return [payload]
    allowed = None if matcher in (None, "", "*") else set(matcher.split("|"))
    name = payload.get("tool_name")
    ti = payload.get("tool_input")
    calls = []
    text = None
    if name == "Bash" and isinstance(ti, dict):
        text = ti.get("command")
        if allowed is None or "Bash" in allowed:
            calls.append(payload)
    elif name in PATCH_TOOLS:
        text = ti if isinstance(ti, str) else " ".join(str(v) for v in ti.values() if isinstance(v, str)) \
            if isinstance(ti, dict) else None
    elif allowed is None or name in allowed:
        calls.append(payload)
    if allowed is None or allowed & {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else ""
        files = patch_files(text)
        if len(files) > MAX_FILES:
            raise TooMany()
        for tool, path in files:
            if allowed is not None and tool not in allowed:
                tool = "Edit" if "Edit" in allowed else "Write"
            p = path if os.path.isabs(path) else os.path.join(cwd, path)
            calls.append({**payload, "tool_name": tool, "tool_input": {"file_path": p}})
    return calls


def turn_calls(rollout, turn_id):
    ""
    try:
        with open(rollout, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - MAX_ROLLOUT_TAIL))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except (OSError, TypeError, ValueError):
        return []
    rows = []
    for l in lines:
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if isinstance(r, dict) and isinstance(r.get("payload"), dict):
            rows.append(r)
    start = 0
    for i, r in enumerate(rows):
        p = r["payload"]
        if r.get("type") == "event_msg" and p.get("type") == "task_started" and (not turn_id or p.get("turn_id") == turn_id):
            start = i
    return [str(r["payload"].get("arguments", ""))[:20000] for r in rows[start:]
            if r.get("type") == "response_item" and r["payload"].get("type") == "function_call"][:500]


def stop_payload(payload, tmp):
    ""
    msg = payload.get("last_assistant_message")
    content = [{"type": "text", "text": msg if isinstance(msg, str) else ""}]
    for a in turn_calls(payload.get("transcript_path"), payload.get("turn_id")):
        content.append({"type": "tool_use", "name": "shell", "input": {"command": a}})
    path = os.path.join(tmp, "transcript.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "message": {"role": "user", "content": "turn"}}) + "\n")
        f.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": content}}) + "\n")
    return {**payload, "transcript_path": path}



def run_child(command, stdin_text, timeout):
    ""
    try:
        p = subprocess.Popen(["sh", "-c", command], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=True)
    except OSError as e:
        return "", str(e), 127, "spawn"
    try:
        out, err = p.communicate(stdin_text.encode("utf-8", "replace"), timeout=timeout)
        how = ""
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        out, err = p.communicate()
        how = "timeout"
    except OSError:
        out, err, how = b"", b"", ""
    dec = lambda b: b[:MAX_CHILD_OUT].decode("utf-8", "replace")
    return dec(out), dec(err), p.returncode if p.returncode is not None else 1, how


def verdict(event, out, err, code, how, label):
    ""
    v = {"deny": None, "block": None, "messages": [], "context": []}
    if how:
        v["messages"].append(f"{label}: {how} (the hook did not answer; this call was NOT checked by it)")
        return v
    if code == 2:
        reason = (err.strip() or out.strip() or f"{label} refused (exit 2)")[:2000]
        if event == "PreToolUse":
            v["deny"] = reason
        elif event in ("Stop", "UserPromptSubmit"):
            v["block"] = reason
        else:
            v["messages"].append(f"{label}: {reason}")
        return v
    if code != 0:
        v["messages"].append(f"{label}: failed (exit {code}): {err.strip()[-300:]} (NOT checked by it)")
        return v
    text = out.strip()
    if not text:
        return v
    try:
        d = json.loads(text)
    except ValueError:
        d = None
    if not isinstance(d, dict):
        if event in ("SessionStart", "UserPromptSubmit"):
            v["context"].append(text)
        return v
    hso = d.get("hookSpecificOutput") if isinstance(d.get("hookSpecificOutput"), dict) else {}
    pd = hso.get("permissionDecision")
    if event == "PreToolUse" and (pd in ("deny", "ask") or d.get("decision") == "block"):
        reason = hso.get("permissionDecisionReason") or d.get("reason") or f"{label} refused this call"
        v["deny"] = (f"(it asked; Codex cannot ask) " if pd == "ask" else "") + str(reason)
    if event in ("Stop", "UserPromptSubmit") and d.get("decision") == "block":
        v["block"] = str(d.get("reason") or f"{label} blocked this")
    if isinstance(hso.get("additionalContext"), str) and event in ("SessionStart", "UserPromptSubmit"):
        v["context"].append(hso["additionalContext"])
    if isinstance(d.get("systemMessage"), str) and d["systemMessage"]:
        v["messages"].append(d["systemMessage"])
    return v


def combine(event, verdicts):
    ""
    deny = [v["deny"] for v in verdicts if v["deny"]]
    block = [v["block"] for v in verdicts if v["block"]]
    msgs = [m for v in verdicts for m in v["messages"]]
    ctx = [c for v in verdicts for c in v["context"]]
    out = {}
    if deny and event == "PreToolUse":
        out["hookSpecificOutput"] = {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": "\n".join(deny)}
    if block and event in ("Stop", "UserPromptSubmit"):
        out["decision"] = "block"
        out["reason"] = "\n".join(block)
    if msgs:
        out["systemMessage"] = "\n".join(dict.fromkeys(msgs))
    if out:
        return json.dumps(out, ensure_ascii=False), 0
    return "\n".join(ctx), 0


def run(event, matcher, cond, timeout, command, raw, label=None):
    ""
    label = label or (command.split() or ["hook"])[0].rsplit("/", 1)[-1]
    if len(raw) > MAX_PAYLOAD:
        if event == "PreToolUse":
            return combine(event, [{"deny": f"{label}: this call is over {MAX_PAYLOAD // 1048576} MiB: too big to check, "
                                              "refused. Split it, or put the text in a file.",
                                    "block": None, "messages": [], "context": []}])
        return combine(event, [{"deny": None, "block": None, "context": [],
                                "messages": [f"{label}: payload over {MAX_PAYLOAD // 1048576} MiB: NOT checked"]}])
    try:
        payload = json.loads(raw.decode("utf-8", "replace")) if raw.strip() else None
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        return combine(event, [{"deny": None, "block": None, "context": [],
                                "messages": [f"{label}: the payload from Codex is empty or not an object: NOT checked"]}])
    tmp = tempfile.mkdtemp(prefix="codex-hooks-")
    try:
        try:
            calls = claude_calls(event, payload, matcher)
        except TooMany:
            if event == "PreToolUse":
                return combine(event, [{"deny": f"{label}: this patch touches over {MAX_FILES} files: too many to check, "
                                                  "refused. Split it.", "block": None, "messages": [], "context": []}])
            return combine(event, [{"deny": None, "block": None, "context": [],
                                    "messages": [f"{label}: a patch over {MAX_FILES} files: NOT checked"]}])
        if event == "Stop":
            calls = [stop_payload(c, tmp) for c in calls]
        if cond:
            calls = [c for c in calls if c.get("tool_name") == "Bash"
                     and if_matches(cond, (c.get("tool_input") or {}).get("command"))]
        per = max(1.0, (timeout or 10) / max(1, len(calls)) - 0.5)
        verdicts = []
        for c in calls:
            out, err, code, how = run_child(command, json.dumps(c, ensure_ascii=False), per)
            verdicts.append(verdict(event, out, err, code, how, label))
            if verdicts[-1]["deny"]:
                break
        return combine(event, verdicts)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)



DENY_FILE = "codex-deny.json"


def deny_pattern(rule):
    ""
    m = re.fullmatch(r"Bash\((.*)\)", rule.strip(), re.S) if isinstance(rule, str) else None
    if not m:
        return None
    body = m.group(1).strip()
    words = lambda t: r"\s+".join(re.escape(w) for w in t.split())
    if body.endswith(":*"):
        core = body[:-2]
        pieces = [words(core) + ("" if core.split()[-1:] and core.split()[-1].startswith("-") else r"(?![\w-])")]
    else:
        pieces = [words(p) for p in body.split("*") if p.strip()]
    if not pieces:
        return None
    if not body.startswith("*"):
        pieces[0] = r"(?<![\w.-])" + pieces[0]
    return [re.compile(x) for x in pieces]


def _hit(pieces, text):
    pos = 0
    for rx in pieces:
        m = rx.search(text, pos)
        if not m:
            return False
        pos = m.end()
    return True


def _force_push(command, rules):
    ""
    if not any(isinstance(r, str) and r.startswith("Bash(git push") and r.rstrip(")").endswith(("-f:*", "--force:*"))
               for r in rules):
        return False
    for seg in re.split(r"[;&|\n]+", command):
        try:
            toks = shlex.split(seg)
        except ValueError:
            toks = seg.split()
        if "push" in toks and "git" in toks[:toks.index("push")] + [t.rsplit("/", 1)[-1] for t in toks[:1]]:
            tail = toks[toks.index("push") + 1:]
            if any(t == "-f" or t.startswith("--force") or (t.startswith("+") and len(t) > 1 and not t.startswith("+-")) for t in tail):
                return True
    return False


def deny_check(rules, command):
    ""
    if not isinstance(command, str):
        return None
    flat = " ".join(command.split())
    for r in rules:
        pieces = deny_pattern(r)
        if pieces is not None and (_hit(pieces, command) or _hit(pieces, flat)):
            return r
    return "Bash(git push --force:*)" if _force_push(command, rules) else None


def deny_main(rules_path, raw):
    ""
    reason = None
    try:
        with open(os.path.expanduser(rules_path), encoding="utf-8") as f:
            rules = json.load(f)["rules"]
        if not isinstance(rules, list):
            raise ValueError("rules is not a list")
    except (OSError, ValueError, KeyError, TypeError) as e:
        return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                           "permissionDecisionReason": f"role deny gate: its rules ({rules_path}) cannot be read "
                                                       f"({e.__class__.__name__}): shell commands are refused until "
                                                       "`onboard --kit --agent codex --write` is run again"}}), 0
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        data = None
    ti = data.get("tool_input") if isinstance(data, dict) else None
    command = ti.get("command") if isinstance(ti, dict) else None
    if isinstance(command, str) and len(command) > MAX_COMMAND:
        hit = f"a command over {MAX_COMMAND // 1024} KiB (too long to check)"
    else:
        hit = deny_check(rules, command)
    if hit:
        reason = (f"role deny gate: your role may not run this ({hit.replace('Bash(', '').rstrip(')')}). Do not reach the same "
                  "effect another way; say what you needed and why, and let the person decide. If these words are only text "
                  "(a note, a commit message), put the text in a file: write it with your file tool, then `git commit -F <file>` "
                  "(or `gh ... --body-file <file>`).")
        return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                  "permissionDecisionReason": reason}}), 0
    return "", 0


def stale_hooks(want, have):
    ""
    def tail(c):
        return c.split(" -- ", 1)[1] if isinstance(c, str) and f"/{SHIM} run " in c and " -- " in c else None
    mapped = {}
    for event, entries in (want or {}).items():
        for e in entries if isinstance(entries, list) else []:
            for h in (e.get("hooks") or []) if isinstance(e, dict) else []:
                if isinstance(h, dict) and tail(h.get("command")):
                    mapped.setdefault((event, tail(h["command"])), []).append(h["command"])
    now = {h.get("command") for es in (want or {}).values() if isinstance(es, list) for e in es if isinstance(e, dict)
           for h in (e.get("hooks") or []) if isinstance(h, dict)}
    out = {}
    for event, entries in ((have or {}).get("hooks") or {}).items() if isinstance((have or {}).get("hooks"), dict) else []:
        for e in entries if isinstance(entries, list) else []:
            for h in (e.get("hooks") or []) if isinstance(e, dict) and isinstance(e.get("hooks"), list) else []:
                c = h.get("command") if isinstance(h, dict) else None
                if tail(c) and c not in now and mapped.get((event, tail(c))):
                    out[c] = mapped[(event, tail(c))][0]
    return out



class NotChecked(Exception):
    ""


def app_server(codex_home, requests, codex="codex", timeout=30):
    ""
    env = dict(os.environ, CODEX_HOME=codex_home)
    try:
        p = subprocess.Popen([codex, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, env=env, cwd=codex_home, start_new_session=True)
    except OSError as e:
        raise NotChecked(f"cannot run {codex}: {e.strerror or e}")
    deadline = time.time() + timeout
    buf = b""

    def send(m):
        p.stdin.write((json.dumps(m) + "\n").encode())
        p.stdin.flush()

    def recv(i):
        nonlocal buf
        while True:
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if isinstance(d, dict) and d.get("id") == i and "method" not in d:
                    if "error" in d:
                        raise NotChecked(f"codex app-server refused {i}: {str(d['error'])[:200]}")
                    return d.get("result")
            left = deadline - time.time()
            if left <= 0:
                raise NotChecked("codex app-server did not answer in time")
            r, _, _ = select.select([p.stdout], [], [], left)
            if not r:
                raise NotChecked("codex app-server did not answer in time")
            chunk = os.read(p.stdout.fileno(), 65536)
            if not chunk:
                raise NotChecked("codex app-server ended before answering")
            buf += chunk
            if len(buf) > 16 * 1024 * 1024:
                raise NotChecked("codex app-server answered with too much")

    try:
        send({"id": 0, "method": "initialize", "params": {"clientInfo": {"name": "iphtah-kit", "version": "1"}}})
        recv(0)
        send({"method": "initialized"})
        out = []
        for n, (method, params) in enumerate(requests, 1):
            send({"id": n, "method": method, "params": params})
            out.append(recv(n))
        return out
    except (OSError, BrokenPipeError) as e:
        raise NotChecked(f"codex app-server: {e}")
    finally:
        try:
            p.stdin.close()
        except OSError:
            pass
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except OSError:
            pass
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                pass
            p.wait()
        try:
            p.stdout.close()
        except OSError:
            pass


KIT_BIN = "~/.claude/iphtah-kit/bin/"


def is_kit_command(command):
    ""
    if not isinstance(command, str) or not command.startswith(f"python3 {KIT_BIN}{SHIM} run ") or " -- " not in command:
        return False
    try:
        tail = shlex.split(command.split(" -- ", 1)[1])
    except ValueError:
        return False
    return len(tail) == 1 and (tail[0].startswith(KIT_BIN) or tail[0].startswith(f"python3 {KIT_BIN}"))


def kit_hooks(codex_home, codex="codex", timeout=30):
    ""
    res = app_server(codex_home, [("hooks/list", {"cwds": [codex_home]})], codex, timeout)[0]
    want = os.path.realpath(os.path.join(codex_home, "hooks.json"))
    out = []
    for entry in (res or {}).get("data") or []:
        for h in entry.get("hooks") or []:
            if not isinstance(h, dict) or not isinstance(h.get("command"), str):
                continue
            src = h.get("sourcePath")
            if (isinstance(src, str) and os.path.realpath(src) == want) and is_kit_command(h["command"]):
                out.append({"key": h.get("key"), "event": h.get("eventName"),
                            "status": h.get("trustStatus") if h.get("enabled", True) else "disabled",
                            "hash": h.get("currentHash")})
    return out


def trust(codex_home, codex="codex", timeout=30):
    ""
    todo = [h for h in kit_hooks(codex_home, codex, timeout) if h["status"] in ("untrusted", "modified") and h["key"] and h["hash"]]
    if todo:
        app_server(codex_home, [("config/batchWrite", {"edits": [{"keyPath": "hooks.state", "mergeStrategy": "upsert",
                                                               "value": {h["key"]: {"trusted_hash": h["hash"]} for h in todo}}]})],
                   codex, timeout)
    return len(todo)



def home_of(a):
    ""
    h = a.codex_home or os.environ.get("CODEX_HOME")
    if not h:
        sys.exit("codex hooks: no Codex home: pass --codex-home DIR or set CODEX_HOME (trust writes DIR/config.toml, so the "
                 "home is never guessed)")
    return os.path.expanduser(h)


USAGE = """The kit's hooks on Codex CLI: the Claude hooks of one source, run through this shim.

    python3 _codex_hooks.py run --event E [--matcher M] [--if COND] [--timeout S] -- COMMAND
        What a hook of ~/.codex/hooks.json runs: it reads Codex's payload on stdin, runs COMMAND (the Claude hook's own
        command) with the payload the kit's tools read, and answers Codex. Always exit 0.
    python3 _codex_hooks.py deny --rules FILE
        The role's deny gate: refuses a shell command that holds one of the rules of FILE, and refuses when in doubt.
    python3 _codex_hooks.py status [--codex-home DIR] [--codex PATH]
        Whether Codex trusts the kit's hooks (it skips an untrusted one without a word). Exit 0 all trusted, 1 some are not
        (or none are installed), 3 not checked.
    python3 _codex_hooks.py trust [--codex-home DIR] [--codex PATH]
        Records Codex's trust for the kit's untrusted or modified hooks, and for no other. Run it after each install.
DIR is --codex-home or $CODEX_HOME, with no default."""


def main(argv=None):
    ap = argparse.ArgumentParser(description=USAGE, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--event", required=True, choices=EVENTS)
    r.add_argument("--matcher")
    r.add_argument("--if", dest="cond")
    r.add_argument("--timeout", type=float, default=10)
    r.add_argument("command", nargs=argparse.REMAINDER)
    d = sub.add_parser("deny")
    d.add_argument("--rules", required=True)
    for name in ("status", "trust"):
        s = sub.add_parser(name)
        s.add_argument("--codex-home")
        s.add_argument("--codex", default="codex")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        cmd = a.command[1:] if a.command[:1] == ["--"] else a.command
        if len(cmd) != 1:
            ap.error("run: the command goes after --, as one string")
        out, code = run(a.event, a.matcher, a.cond, a.timeout, cmd[0], sys.stdin.buffer.read(MAX_PAYLOAD + 1))
        if out:
            print(out)
        return code
    if a.cmd == "deny":
        out, code = deny_main(a.rules, sys.stdin.buffer.read(MAX_PAYLOAD + 1))
        if out:
            print(out)
        return code
    home = home_of(a)
    try:
        if a.cmd == "status":
            hooks = kit_hooks(home, a.codex)
            bad = [h for h in hooks if h["status"] != "trusted"]
            for h in hooks:
                print(f"{h['status']:10} {h['event']:16} {h['key']}")
            if not hooks:
                print(f"codex hooks: no kit hook in {home}/hooks.json: nothing runs (onboard --kit --agent codex --write)")
                return 1
            if bad:
                print(f"codex hooks: {len(bad)} of {len(hooks)} kit hooks are NOT trusted: Codex skips them, silently. "
                      f"Run: python3 {sys.argv[0]} trust")
                return 1
            print(f"codex hooks: all {len(hooks)} kit hooks are trusted.")
            return 0
        n = trust(home, a.codex)
        print(f"codex hooks: {n} hook(s) trusted in {home}/config.toml (the kit's, no other).")
        return 0
    except NotChecked as e:
        print(f"codex hooks: NOT checked: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
