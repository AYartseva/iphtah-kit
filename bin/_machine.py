""
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys

DEFAULT_FILE = "~/.claude/iphtah-kit/machine.json"

FORMULAS = {
    "building_agents": "max(1, cores - 1)",
    "quiet_load": "cores",
    "maven_slots": "max(1, cores // 4)",
    "vitest_slots": "max(1, cores // 4)",
    "py_slots": "max(1, cores // 4)",
    "pysuite_slots": "max(1, cores // 8)",
    "platform_builds": "max(1, min(cores // 2, ram_gib // 8))",
}
MEANING = {
    "building_agents": "sub-agents building at once (queue-tick and night-check --slots)",
    "quiet_load": "1-minute load under which the machine counts as quiet (when-quiet --load)",
    "maven_slots": "targeted Maven runs at once (run-queued maven)",
    "vitest_slots": "targeted vitest runs at once (run-queued vitest)",
    "py_slots": "Python test runs at once (run-queued py; mutant-check's Python mode, 13/10/2026)",
    "pysuite_slots": "light repositories' full Python suites at once (run-queued pysuite, taken by merge-check, 14/10/2026)",
    "platform_builds": "platform builds at once (each starts its own Testcontainers database)",
}
TOOLS = ("docker", "gh", "node", "pnpm", "python3", "uv")


def machine_file():
    return os.path.expanduser(os.environ.get("IPHTAH_MACHINE_FILE", DEFAULT_FILE))


def derive(m):
    ""
    cores, ram = int(m["cores"]), int(m["ram_gib"])
    return {"building_agents": max(1, cores - 1),
            "quiet_load": cores,
            "maven_slots": max(1, cores // 4),
            "vitest_slots": max(1, cores // 4),
            "py_slots": max(1, cores // 4),
            "pysuite_slots": max(1, cores // 8),
            "platform_builds": max(1, min(cores // 2, ram // 8))}


def _version(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"\d+(\.\d+)+", out.stdout + out.stderr)
    return m.group(0) if m else "?"


def _which(name):
    ""
    found = shutil.which(name)
    if found:
        return found
    for p in sorted(glob.glob(os.path.expanduser(f"~/.nvm/versions/node/*/bin/{name}")), reverse=True):
        return p
    p = os.path.expanduser(f"~/.local/bin/{name}")
    return p if os.access(p, os.X_OK) else None


def _javas(root="/usr/lib/jvm"):
    ""
    out = {}
    for d in sorted(set(os.path.realpath(p) for p in glob.glob(os.path.join(root, "*")) if os.path.isdir(p))):
        ver = None
        try:
            for line in open(os.path.join(d, "release")):
                if line.startswith("JAVA_VERSION="):
                    ver = line.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
        if ver is None and os.access(os.path.join(d, "bin", "java"), os.X_OK):
            ver = _version([os.path.join(d, "bin", "java"), "-version"])
        if ver:
            major = ver.split(".")[0]
            if major == "1":
                major = ver.split(".")[1]
            out[f"java-{major}"] = ver
    return out


def _ram_gib():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return round(int(line.split()[1]) / 1024 / 1024, 1)
    except OSError:
        pass
    return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30, 1)


def _cores():
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        return os.cpu_count() or 1


def measure(full=True):
    ""
    fake = os.environ.get("IPHTAH_MACHINE_MEASURES")
    if fake:
        with open(fake) as f:
            return json.load(f)
    cores = _cores()
    if not full:
        return {"cores": cores, "ram_gib": _ram_gib()}
    st = os.statvfs(os.path.expanduser("~"))
    osname = platform.system()
    try:
        rel = dict(l.rstrip().split("=", 1) for l in open("/etc/os-release") if "=" in l)
        osname = rel.get("PRETTY_NAME", osname).strip('"')
    except OSError:
        pass
    tools = {}
    for t in TOOLS:
        p = _which(t)
        tools[t] = _version([p, "--version"]) if p else None
    tools.update(_javas())
    return {"cores": cores, "ram_gib": _ram_gib(), "disk_free_gib": round(st.f_bavail * st.f_frsize / 2 ** 30, 1),
            "arch": platform.machine(), "os": osname, "tools": tools}


def read_file(path=None):
    path = path or machine_file()
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def machine_limits(path=None, measures=None):
    ""
    data = read_file(path)
    if data is None:
        return derive(measures if measures is not None else measure(full=False))
    limits = derive(data["measures"])
    limits.update(data.get("limits") or {})
    for k, v in (data.get("overrides") or {}).items():
        if k in limits and v is not None:
            limits[k] = v
    return limits


def limit(name, path=None):
    return machine_limits(path)[name]


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "get" and sys.argv[2] in FORMULAS:
        print(limit(sys.argv[2]))
        sys.exit(0)
    sys.exit("usage: _machine.py get <" + "|".join(FORMULAS) + ">")
