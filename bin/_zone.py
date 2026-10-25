""
import os
from zoneinfo import ZoneInfo

DEFAULT = "Europe/Paris"


def home_zone(env=None):
    ""
    name = (os.environ if env is None else env).get("IPHTAH_TZ") or DEFAULT
    try:
        return name, ZoneInfo(name)
    except (ValueError, KeyError, OSError):
        return DEFAULT, ZoneInfo(DEFAULT)


def label(name):
    ""
    return name.rsplit("/", 1)[-1].replace("_", " ")
