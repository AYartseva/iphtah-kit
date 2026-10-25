""
import datetime as dt
import fcntl
import json
import os
import subprocess

FILES = {"capabilities": "rows.json", "areaOwners": "area-owners.json", "questions": "questions.json",
         "milestones": "milestones.json"}
MIRROR_WRITES = "this kit has no tool that writes it: give the client a map_dir"
MIRROR_COPIES = "this kit has no tool that copies it: give the client a map_dir"
MIRROR = {"capabilities": "map-rows.json", "areaOwners": "area-owners.json", "questions": "map-questions.json",
          "milestones": None}


class Map:
    ""

    def __init__(self, client, project, folder):
        self.client, self.project, self.folder = client, project or {}, folder
        self.state = os.path.expanduser(self.project.get("state_dir") or f"~/.local/state/{client}")
        md = self.project.get("map_dir")
        self.files = os.path.normpath(os.path.join(folder, os.path.expanduser(md))) if md else None

    def path(self, collection):
        ""
        if self.files:
            return os.path.join(self.files, FILES[collection])
        name = MIRROR[collection]
        return os.path.join(self.state, name) if name else None

    def where(self, collection="capabilities"):
        ""
        p = self.path(collection)
        return f"{p} (map_dir)" if self.files else f"{p} ({MIRROR_WRITES})"

    def exists(self, collection):
        p = self.path(collection)
        return bool(p) and os.path.exists(p)

    def load(self, collection, default=None):
        ""
        p = self.path(collection)
        if not p or not os.path.exists(p):
            return default
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def age_h(self, now, collection="capabilities"):
        ""
        if self.files:
            return 0.0
        t = now.timestamp() if isinstance(now, dt.datetime) else float(now)
        return (t - os.path.getmtime(self.path(collection))) / 3600

    def is_fresh(self, now, max_h, collection="capabilities"):
        return bool(self.files) or self.age_h(now, collection) <= max_h

    def write(self, collection, docs, why):
        ""
        return self.write_all({collection: docs}, why)

    def write_all(self, collections, why):
        ""
        return self.change([], lambda _: collections, why)

    def change(self, names, fn, why, then=None):
        ""
        if not self.files:
            raise ValueError(f"{self.client} has no map_dir: its map is the artifact ({MIRROR_COPIES})")
        why = " ".join(str(why or "").split())
        if not why:
            raise ValueError("a map write says why")
        for collection in names:
            if collection not in FILES:
                raise ValueError(f"unknown collection {collection!r}")
        os.makedirs(self.state, exist_ok=True)
        with open(os.path.join(self.state, "map.lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            out = fn({c: self.load(c, []) for c in names})
            if not out:
                return None
            os.makedirs(self.files, exist_ok=True)
            texts = {}
            for collection, docs in out.items():
                if collection not in FILES:
                    raise ValueError(f"unknown collection {collection!r}")
                ids = [d.get("id") if isinstance(d, dict) else None for d in docs]
                if any(not isinstance(i, str) or not i for i in ids):
                    raise ValueError(f"{collection}: every doc has a string id")
                if len(set(ids)) != len(ids):
                    raise ValueError(f"{collection}: two docs with the same id")
                docs = sorted(docs, key=lambda d: d["id"] + ".json")
                texts[self.path(collection)] = json.dumps(docs, ensure_ascii=False, indent=1) + "\n"
            for out_path, text in texts.items():
                tmp = os.path.join(self.files, f".{os.path.basename(out_path)}.tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(text)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, out_path)
            sha = _commit(self.files, list(texts), f"map: {why}")
            if then:
                then(sha)
            return sha


def _git(cwd, *args):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)


def _commit(cwd, paths, message):
    rel = [os.path.relpath(p, cwd) for p in paths]
    p = _git(cwd, "add", "--", *rel)
    if p.returncode != 0:
        raise RuntimeError(f"git add {' '.join(rel)}: {(p.stderr or p.stdout).strip()}")
    if _git(cwd, "diff", "--cached", "--quiet", "--", *rel).returncode == 0:
        return None
    p = _git(cwd, "commit", "-q", "-m", message, "--", *rel)
    if p.returncode != 0:
        raise RuntimeError(f"git commit {' '.join(rel)}: {(p.stderr or p.stdout).strip()}")
    return _git(cwd, "rev-parse", "HEAD").stdout.strip()


def of(client, project=None, clients=None):
    ""
    folder = os.path.join(os.path.expanduser(clients or os.environ.get("IPHTAH_CLIENTS", "~/.claude/iphtah-kit/clients")), client)
    if project is None:
        with open(os.path.join(folder, "project.json"), encoding="utf-8") as f:
            project = json.load(f)
    return Map(client, project, folder)


def write(client, collection, docs, why, clients=None):
    ""
    return of(client, clients=clients).write(collection, docs, why)
