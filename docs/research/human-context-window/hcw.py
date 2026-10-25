#!/usr/bin/env python3
"""How much context does a human developer hold at once? Measured from a git history.
"""
import bisect
import collections
import json
import math
import re
import statistics
import subprocess
import sys

SEP = "\x1e"

MECH_FILE = re.compile(
    r"(^|/)(yarn\.lock|package-lock\.json|Gemfile\.lock|poetry\.lock|Pipfile\.lock|pnpm-lock\.yaml"
    r"|npm-shrinkwrap\.json|composer\.lock|Cargo\.lock|go\.sum)$"
    r"|(^|/)requirements/.*\.txt$"
    r"|(^|/)(locale|locales|translations|i18n)/"
    r"|\.(po|pot|mo)$"
    r"|(^|/)(vendor|vendored|third|third_party|thirdparty|node_modules|bower_components)/"
    r"|\.min\.(js|css)$|\.map$"
    r"|(^|/)(generated|dist)/"
    r"|(^|/)public/javascripts/(jquery|jstoolbar/lang|i18n|raphael|select2|tablesort)"
    r"|(^|/)public/(javascripts|stylesheets)/.*jquery"
    r"|(^|/)lib/plugins/(rfpdf|gravatar|open_id_authentication|awesome_nested_set|"
    r"acts_as_tree|coderay|prototype_legacy_helper|classic_pagination|ruby-net-ldap)"
    r"|(^|/)(fixtures|test_fixtures|stripe_fixtures)/.*\.(json|txt|eml|html|xml)$|(^|/)test/fixtures/files/"
    r"|(^|/)(casperjs|svg|lib/SVG|prototype|scriptaculous)/|(^|/)public/javascripts/(prototype|effects|dragdrop|controls)\.js$"
    r"|(^|/)(api_docs/)?.*\.(png|jpg|jpeg|gif|ico|svg|woff2?|ttf|eot|otf|pdf|zip|gz)$",
    re.I,
)
MECH_MSG = re.compile(
    r"\b(bump(ed)? (the )?version|version bump|release \d|\d+\.\d+(\.\d+)? release|"
    r"updates? for \d+\.\d+(\.\d+)? release|prepare.* release|"
    r"tag(ged)? (version|v?\d)|update(d)? (the )?(translations?|locales?)|translations? update|"
    r"(re)?format(ted)? (with|using) |reformat|prettier|\bblack\b|isort|pyupgrade|codemod|"
    r"auto-?generated|regenerate|vendor(ed)?\b|upgrade .* to \d+\.\d+|upgrade .* to (version|latest)|"
    r"updated? .*(library|javascripts)|merged? .*\bbranch\b|"
    r"(update|upgrade|bump)s? (\S+ )?(dependenc|lockfile|yarn|npm|gems?\b|requirements))",
    re.I,
)
FIX_RE = re.compile(
    r"\b(fix|fixe[sd]|fixing|bugs?|bugfix|hotfix|revert(s|ed)?|oops|typo|regression|broken|"
    r"crash(es|ed)?|wrong|incorrect)\b",
    re.I,
)
ISSUE_CLOSE = re.compile(r"\bfix(es|ed)?:? #\d+", re.I)
STYLE_RE = re.compile(r"rubocop|offen[cs]es?\b|\blint\b|eslint|flake8|mypy|pep8|whitespace|indentation|trailing", re.I)
SHA_RE = re.compile(r"\b([0-9a-f]{7,40})\b")
SVN_REF_RE = re.compile(r"\br(\d{2,6})\b")
SVN_ID_RE = re.compile(r"git-svn-id: \S+@(\d+) ")
REVERT_RE = re.compile(r"\brevert", re.I)
PATCH_BY_RE = re.compile(r"(?:patch|contributed) by ([^.(\n,]+)", re.I)


def extract(repo, out, until="2022-01-01"):
    fmt = SEP + "%H%x1f%aN%x1f%aE%x1f%at%x1f%cN%x1f%ct%x1f%s%x1f%b%x1d"
    cmd = ["git", "-C", repo, "log", "--no-merges", "--use-mailmap", "-M", "--numstat",
           "--format=" + fmt]
    import datetime
    limit = datetime.datetime.fromisoformat(until).replace(tzinfo=datetime.timezone.utc).timestamp()
    cmd.append("--before=" + datetime.datetime.fromtimestamp(limit + 182 * 86400, datetime.timezone.utc).date().isoformat())
    raw = subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=True).stdout
    n = 0
    with open(out, "w") as f:
        for rec in raw.split(SEP)[1:]:
            head, _, stats = rec.partition("\x1d")
            sha, an, ae, at, cn, ct, subj, body = head.split("\x1f")
            if int(at) >= limit:
                continue
            files = []
            for line in stats.strip().splitlines():
                parts = line.split("\t")
                if len(parts) != 3:
                    continue
                a, d, path = parts
                rename = "=>" in path
                path = resolve_rename(path)
                binary = a == "-"
                files.append([path, 0 if binary else int(a), 0 if binary else int(d), rename, binary])
            f.write(json.dumps({"sha": sha, "author": an, "email": ae.lower(), "at": int(at),
                                "committer": cn, "ct": int(ct), "subject": subj,
                                "body": body[:2000], "files": files}) + "\n")
            n += 1
    print(f"{out}: {n} commits")


def resolve_rename(path):
    ""
    m = re.match(r"(.*)\{(.*) => (.*)\}(.*)", path)
    if m:
        return re.sub("//+", "/", m.group(1) + m.group(3) + m.group(4))
    if " => " in path:
        return path.split(" => ")[1]
    return path


def module_of(path):
    parts = path.split("/")
    if len(parts) == 1:
        return "(root)"
    if len(parts) == 2:
        return parts[0]
    return parts[0] + "/" + parts[1]


def is_test(path):
    return bool(re.search(r"(^|/)(tests?|spec|frontend_tests|test_fixtures|fixtures)/|_test\.|test_[^/]*\.py$|\.test\.", path))


def classify(c):
    ""
    files = c["files"]
    total = sum(a + d for _, a, d, _, _ in files)
    mech_lines = sum(a + d for p, a, d, _, b in files if b or MECH_FILE.search(p))
    human = [(p, a, d) for p, a, d, r, b in files if not (b or MECH_FILE.search(p))]
    renames = sum(1 for _, a, d, r, _ in files if r and a + d <= 2)
    reason = None
    if not files:
        reason = "empty"
    elif MECH_MSG.search(c["subject"]):
        reason = "message"
    elif len(files) >= 10 and renames >= 0.9 * len(files):
        reason = "mass-rename"
    elif not human or (total > 0 and mech_lines >= 0.8 * total):
        reason = "mechanical-files"
    c["mech"] = reason
    c["hfiles"] = [p for p, _, _ in human]
    c["lines"] = sum(a + d for _, a, d in human)
    c["added"] = sum(a for _, a, _ in human)
    c["modules"] = sorted({module_of(p) for p, _, _ in human})
    c["code_modules"] = sorted({module_of(p) for p, _, _ in human if not is_test(p)})
    c["tops"] = sorted({p.split("/")[0] if "/" in p else "(root)" for p, _, _ in human})
    c["has_test"] = any(is_test(p) for p, _, _ in human)
    subj = c["subject"]
    c["is_fix"] = is_fix(subj)
    c["is_revert"] = bool(REVERT_RE.search(subj))
    m = SVN_ID_RE.search(c["body"])
    c["svn"] = int(m.group(1)) if m else None


def is_fix(subj):
    return bool(FIX_RE.search(ISSUE_CLOSE.sub("", subj))) and not STYLE_RE.search(subj)


def pct(xs, q):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def dist(xs):
    return {"n": len(xs), "median": pct(xs, .5), "p75": pct(xs, .75), "p90": pct(xs, .9),
            "p99": pct(xs, .99), "mean": statistics.fmean(xs) if xs else float("nan")}


LINE_BUCKETS = [(0, 0), (1, 5), (6, 20), (21, 50), (51, 100), (101, 200), (201, 400),
                (401, 800), (801, 1600), (1601, 10**9)]
FILE_BUCKETS = [(1, 1), (2, 2), (3, 3), (4, 5), (6, 8), (9, 13), (14, 20), (21, 40), (41, 10**9)]


def bucket(v, buckets):
    for lo, hi in buckets:
        if lo <= v <= hi:
            return f"{lo}-{hi}" if hi < 10**9 else f"{lo}+"
    return None


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def analyze(path, name):
    commits = [json.loads(l) for l in open(path)]
    commits.sort(key=lambda c: c["at"])
    for c in commits:
        classify(c)
    human = [c for c in commits if c["mech"] is None and c["hfiles"]]
    mech = collections.Counter(c["mech"] for c in commits if c["mech"])
    mech_human_empty = sum(1 for c in commits if c["mech"] is None and not c["hfiles"])
    R = {"name": name, "commits_total": len(commits), "mechanical": dict(mech),
         "human": len(human), "first": min(c["at"] for c in commits),
         "last": max(c["at"] for c in commits), "dropped_no_human_files": mech_human_empty}

    files = [len(c["hfiles"]) for c in human]
    lines = [c["lines"] for c in human]
    mods = [len(c["modules"]) for c in human]
    cmods = [len(c["code_modules"]) for c in human]
    R["size"] = {"files": dist(files), "lines": dist(lines), "modules": dist(mods),
                 "code_modules": dist(cmods), "top_dirs": dist([len(c["tops"]) for c in human])}
    R["width"] = {k: share([v for v in mods], k) for k in (1, 2, 3)}
    R["width_code"] = {k: share([v for v in cmods], k) for k in (0, 1, 2, 3)}
    R["with_tests"] = sum(c["has_test"] for c in human) / len(human)

    import datetime
    by_year = collections.defaultdict(list)
    for c in human:
        by_year[datetime.datetime.fromtimestamp(c["at"], datetime.timezone.utc).year].append(c)
    R["years"] = {y: {"n": len(cs), "authors": len({c["email"] for c in cs}),
                      "files_med": pct([len(c["hfiles"]) for c in cs], .5),
                      "lines_med": pct([c["lines"] for c in cs], .5),
                      "lines_p90": pct([c["lines"] for c in cs], .9),
                      "modules_mean": statistics.fmean(len(c["modules"]) for c in cs),
                      "one_module": share([len(c["modules"]) for c in cs], 1),
                      "fix_share": sum(c["is_fix"] for c in cs) / len(cs)}
                  for y, cs in sorted(by_year.items())}

    touches = collections.defaultdict(list)
    for i, c in enumerate(human):
        if c["is_fix"]:
            for p in c["hfiles"]:
                touches[p].append((c["at"], i))
    named = named_followups(commits, human)
    for w in (7, 30):
        sec = w * 86400
        for i, c in enumerate(human):
            hits = []
            for p in c["hfiles"]:
                lst = touches.get(p, [])
                j = bisect.bisect_right(lst, (c["at"], 10**9))
                hits.append(j < len(lst) and lst[j][0] <= c["at"] + sec)
            c[f"fu{w}"] = any(hits)
            c[f"fu{w}_files"] = sum(hits)
            c[f"fu{w}_hits"] = hits
    ft, fh = collections.Counter(), collections.Counter()
    for c in human:
        for p, h in zip(c["hfiles"], c["fu7_hits"]):
            ft[p] += 1
            fh[p] += h
    for c in human:
        miss = 1.0
        for p, h in zip(c["hfiles"], c["fu7_hits"]):
            usual = (fh[p] - h) / (ft[p] - 1) if ft[p] > 1 else 0.0
            miss *= 1 - usual
        c["fu7_expected"] = 1 - miss
    for c in human:
        c["named"] = c["sha"] in named

    def table(key, buckets, fn):
        rows = collections.OrderedDict((bucket(lo if lo else 0, buckets), []) for lo, _ in buckets)
        for c in human:
            rows[bucket(fn(c), buckets)].append(c)
        out = []
        for b, cs in rows.items():
            if not cs:
                continue
            n = len(cs)
            nf = sum(len(c["hfiles"]) for c in cs)
            row = {"bucket": b, "n": n, "share": n / len(human),
                   "fu7": sum(c["fu7"] for c in cs) / n,
                   "fu30": sum(c["fu30"] for c in cs) / n,
                   "fu7_per_file": sum(c["fu7_files"] for c in cs) / nf,
                   "fu7_expected": sum(c["fu7_expected"] for c in cs) / n,
                   "named_nonfix": rate([c["named"] for c in cs if not c["is_fix"] and not c["is_revert"]]),
                   "named": sum(c["named"] for c in cs) / n,
                   "named_ci": wilson(sum(c["named"] for c in cs), n),
                   "named_per_kline": 1000 * sum(c["named"] for c in cs) / max(1, sum(c["lines"] for c in cs)),
                   "is_fix": sum(c["is_fix"] for c in cs) / n}
            out.append(row)
        return out

    R["by_lines"] = table("lines", LINE_BUCKETS, lambda c: c["lines"])
    R["by_files"] = table("files", FILE_BUCKETS, lambda c: len(c["hfiles"]))
    MOD_B = [(1, 1), (2, 2), (3, 3), (4, 5), (6, 10**9)]
    R["by_modules"] = table("modules", MOD_B, lambda c: len(c["modules"]))
    R["named_total"] = sum(c["named"] for c in human)
    R["cross"] = cross(human)
    R["series_by_lines"] = series_table(human)
    R["fix_share"] = sum(c["is_fix"] for c in human) / len(human)

    credit = collections.Counter(c["email"] for c in human)
    R["people"] = people(human, credit)
    R["series"] = series(human)
    R["hist_lines_log2"] = log2_hist(lines)
    return R, human


def rate(flags):
    return sum(flags) / len(flags) if flags else float("nan")


def cross(human):
    ""
    LB = [(0, 20), (21, 100), (101, 400), (401, 10**9)]
    MB = [(1, 1), (2, 2), (3, 10**9)]
    out = {}
    for lo, hi in LB:
        for mlo, mhi in MB:
            cs = [c for c in human if lo <= c["lines"] <= hi and mlo <= len(c["modules"]) <= mhi]
            out[f"{bucket(lo, LB)}|{bucket(mlo, MB)}"] = {"n": len(cs), "named": rate([c["named"] for c in cs]),
                                                           "fu7_ratio": (rate([c["fu7"] for c in cs]) /
                                                                         rate([c["fu7_expected"] for c in cs]))
                                                           if cs and rate([c["fu7_expected"] for c in cs]) else float("nan")}
    return out


def share(xs, k):
    return sum(1 for x in xs if x == k) / len(xs) if k < 3 else sum(1 for x in xs if x >= k) / len(xs)


def log2_hist(xs):
    h = collections.Counter(int(math.log2(x)) if x > 0 else -1 for x in xs)
    return {k: h[k] / len(xs) for k in sorted(h)}


def named_followups(all_commits, human):
    ""
    by_prefix = {}
    by_svn = {}
    for c in all_commits:
        by_prefix[c["sha"][:7]] = c
        if c.get("svn"):
            by_svn[c["svn"]] = c
    out = set()
    for c in all_commits:
        text = c["subject"] + "\n" + SVN_ID_RE.sub("", c["body"])
        if not (is_fix(c["subject"]) or REVERT_RE.search(text)):
            continue
        for m in SHA_RE.finditer(text):
            t = by_prefix.get(m.group(1)[:7])
            if t and t["sha"].startswith(m.group(1)) and t["at"] < c["at"] and t["sha"] != c["sha"]:
                out.add(t["sha"])
        if by_svn:
            for m in SVN_REF_RE.finditer(text):
                t = by_svn.get(int(m.group(1)))
                if t and t["at"] <= c["at"] and t["sha"] != c["sha"]:
                    out.add(t["sha"])
    return out


def people(human, credit):
    ranked = credit.most_common()
    total = sum(credit.values())
    core, acc = set(), 0
    for e, n in ranked:
        if acc >= 0.8 * total:
            break
        core.add(e)
        acc += n
    groups = {"core (80 % of commits)": lambda c: c["email"] in core,
              "regular (10+ commits, not core)": lambda c: c["email"] not in core and credit[c["email"]] >= 10,
              "occasional (< 10 commits)": lambda c: credit[c["email"]] < 10}
    out = {"authors": len(credit), "core_size": len(core),
           "top5_share": sum(n for _, n in ranked[:5]) / total,
           "one_commit_authors": sum(1 for _, n in ranked if n == 1)}
    for g, f in groups.items():
        cs = [c for c in human if f(c)]
        if not cs:
            continue
        out[g] = {"commits": len(cs), "authors": len({c["email"] for c in cs}),
                  "lines_med": pct([c["lines"] for c in cs], .5),
                  "lines_p90": pct([c["lines"] for c in cs], .9),
                  "files_med": pct([len(c["hfiles"]) for c in cs], .5),
                  "modules_mean": statistics.fmean(len(c["modules"]) for c in cs),
                  "named": sum(c["named"] for c in cs) / len(cs),
                  "fu7_per_file": sum(c["fu7_files"] for c in cs) / max(1, sum(len(c["hfiles"]) for c in cs))}
    pb = [c for c in human if PATCH_BY_RE.search(c["body"] + " " + c["subject"])]
    own = [c for c in human if not PATCH_BY_RE.search(c["body"] + " " + c["subject"])]
    out["patch_by_share"] = len(pb) / len(human)
    if pb:
        out["patch_by"] = {"n": len(pb), "lines_med": pct([c["lines"] for c in pb], .5),
                           "lines_p90": pct([c["lines"] for c in pb], .9), "named": rate([c["named"] for c in pb]),
                           "contributors": len({PATCH_BY_RE.search(c["body"] + " " + c["subject"]).group(1).strip().lower() for c in pb})}
        out["own"] = {"n": len(own), "lines_med": pct([c["lines"] for c in own], .5),
                      "lines_p90": pct([c["lines"] for c in own], .9), "named": rate([c["named"] for c in own])}
    return out


def series_groups(human, gap=180):
    ordered = sorted(human, key=lambda c: (c["committer"], c["email"], c["ct"]))
    groups, cur = [], []
    for c in ordered:
        if cur and (c["email"] != cur[-1]["email"] or c["committer"] != cur[-1]["committer"]
                    or c["ct"] - cur[-1]["ct"] > gap):
            groups.append(cur)
            cur = []
        cur.append(c)
    if cur:
        groups.append(cur)
    return groups


def series_table(human):
    out = []
    groups = series_groups(human)
    for lo, hi in LINE_BUCKETS[1:]:
        gs = [g for g in groups if lo <= sum(c["lines"] for c in g) <= hi]
        if gs:
            out.append({"bucket": bucket(lo, LINE_BUCKETS), "n": len(gs),
                        "commits_med": pct([len(g) for g in gs], .5),
                        "named": rate([any(c["named"] for c in g) for g in gs])})
    return out


def series(human, gap=180):
    ""
    groups = series_groups(human, gap)
    sizes = [len(g) for g in groups]
    lines = [sum(c["lines"] for c in g) for g in groups]
    files = [len({p for c in g for p in c["hfiles"]}) for g in groups]
    mods = [len({m for c in g for m in c["modules"]}) for g in groups]
    multi = [g for g in groups if len(g) > 1]
    return {"n": len(groups), "commits": dist(sizes), "lines": dist(lines), "files": dist(files),
            "modules": dist(mods), "multi_share": len(multi) / len(groups),
            "commits_in_multi": sum(len(g) for g in multi) / len(human)}


def fmt(x, p=0):
    if isinstance(x, float):
        if math.isnan(x):
            return "-"
        return f"{x:.{p}f}"
    return str(x)


def report_md(R):
    L = [f"## {R['name']}", ""]
    s = R["size"]
    L.append(f"{R['commits_total']} non-merge commits; mechanical removed: {sum(R['mechanical'].values())} "
             f"({', '.join(f'{k} {v}' for k, v in R['mechanical'].items())}); human commits analysed: {R['human']}.")
    L += ["", "| measure | median | P75 | P90 | P99 | mean |", "|---|---|---|---|---|---|"]
    for k in ("files", "lines", "modules", "code_modules", "top_dirs"):
        d = s[k]
        L.append(f"| {k} | {fmt(d['median'])} | {fmt(d['p75'])} | {fmt(d['p90'])} | {fmt(d['p99'])} | {fmt(d['mean'], 1)} |")
    L += ["", "| lines changed | commits | share | follow-up fix 7 d | expected by chance | observed / expected | 30 d | per file 7 d | named by a later fix/revert (95 % CI) | named, non-fix commits | named per 1000 lines |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in R["by_lines"]:
        lo, hi = r["named_ci"]
        L.append(f"| {r['bucket']} | {r['n']} | {100*r['share']:.1f} % | {100*r['fu7']:.0f} % | {100*r['fu7_expected']:.0f} % | "
                 f"{r['fu7']/r['fu7_expected'] if r['fu7_expected'] else float('nan'):.2f} | {100*r['fu30']:.0f} % | "
                 f"{100*r['fu7_per_file']:.1f} % | {100*r['named']:.1f} % ({100*lo:.1f}–{100*hi:.1f}) | {100*r['named_nonfix']:.1f} % | {r['named_per_kline']:.2f} |")
    L += ["", "| files | commits | share | follow-up fix 7 d | per file 7 d | named |", "|---|---|---|---|---|---|"]
    for r in R["by_files"]:
        L.append(f"| {r['bucket']} | {r['n']} | {100*r['share']:.1f} % | {100*r['fu7']:.0f} % | {100*r['fu7_per_file']:.1f} % | {100*r['named']:.1f} % |")
    L += ["", "| modules | commits | share | follow-up fix 7 d | per file 7 d | named |", "|---|---|---|---|---|---|"]
    for r in R["by_modules"]:
        L.append(f"| {r['bucket']} | {r['n']} | {100*r['share']:.1f} % | {100*r['fu7']:.0f} % | {100*r['fu7_per_file']:.1f} % | {100*r['named']:.1f} % |")
    L += ["", "| year | commits | authors | median files | median lines | P90 lines | modules (mean) | 1 module | fix share |",
          "|---|---|---|---|---|---|---|---|---|"]
    for y, d in R["years"].items():
        L.append(f"| {y} | {d['n']} | {d['authors']} | {fmt(d['files_med'])} | {fmt(d['lines_med'])} | {fmt(d['lines_p90'])} | "
                 f"{d['modules_mean']:.2f} | {100*d['one_module']:.0f} % | {100*d['fix_share']:.0f} % |")
    L += ["", "Named rate (and follow-up observed / expected) by size × width:", "",
          "| lines \\ modules | 1 | 2 | 3+ |", "|---|---|---|---|"]
    for lb in ("0-20", "21-100", "101-400", "401+"):
        cells = [R["cross"][f"{lb}|{mb}"] for mb in ("1-1", "2-2", "3+")]
        L.append(f"| {lb} | " + " | ".join(f"{100*d['named']:.1f} % ({d['fu7_ratio']:.2f}; n={d['n']})" for d in cells) + " |")
    L += ["", "Series (≈ pull request) named by a later fix/revert, by total lines:", "",
          "| series lines | series | median commits | named |", "|---|---|---|---|"]
    for r in R["series_by_lines"]:
        L.append(f"| {r['bucket']} | {r['n']} | {fmt(r['commits_med'])} | {100*r['named']:.1f} % |")
    P = R["people"]
    L += ["", f"Authors: {P['authors']}; core (80 % of commits): {P['core_size']}; top 5 make {100*P['top5_share']:.0f} %; "
          f"{P['one_commit_authors']} authors made one commit. Commits crediting a « patch by » someone else: {100*P['patch_by_share']:.0f} %.",
          "", "| group | commits | authors | median lines | P90 lines | median files | modules (mean) | named | per-file follow-up 7 d |",
          "|---|---|---|---|---|---|---|---|---|"]
    for g, d in P.items():
        if isinstance(d, dict) and "commits" in d:
            L.append(f"| {g} | {d['commits']} | {d['authors']} | {fmt(d['lines_med'])} | {fmt(d['lines_p90'])} | {fmt(d['files_med'])} | "
                     f"{d['modules_mean']:.2f} | {100*d['named']:.1f} % | {100*d['fu7_per_file']:.1f} % |")
    if "patch_by" in P:
        a, b = P["patch_by"], P["own"]
        L += ["", f"Credited patches (« Patch by X », {a['contributors']} names): {a['n']} commits, median {fmt(a['lines_med'])} lines, "
              f"P90 {fmt(a['lines_p90'])}, named {100*a['named']:.1f} %; committers' own: {b['n']}, median {fmt(b['lines_med'])}, "
              f"P90 {fmt(b['lines_p90'])}, named {100*b['named']:.1f} %."]
    S = R["series"]
    L += ["", f"Series (same author landed within 3 min, ≈ one pull request): {S['n']}; "
          f"{100*S['multi_share']:.0f} % have 2+ commits, holding {100*S['commits_in_multi']:.0f} % of commits.",
          "", "| series | median | P75 | P90 | P99 |", "|---|---|---|---|---|"]
    for k in ("commits", "files", "lines", "modules"):
        d = S[k]
        L.append(f"| {k} | {fmt(d['median'])} | {fmt(d['p75'])} | {fmt(d['p90'])} | {fmt(d['p99'])} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    if sys.argv[1] == "extract":
        until = sys.argv[sys.argv.index("--until") + 1] if "--until" in sys.argv else "2022-01-01"
        extract(sys.argv[2], sys.argv[3], until)
    elif sys.argv[1] == "analyze":
        src, name, outdir = sys.argv[2:5]
        R, _ = analyze(src, name)
        json.dump(R, open(f"{outdir}/{name}.json", "w"), indent=1, default=str)
        open(f"{outdir}/{name}.md", "w").write(report_md(R))
        print(report_md(R))
    else:
        print(__doc__)
