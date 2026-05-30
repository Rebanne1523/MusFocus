#!/usr/bin/env python3
"""FocusNotifier listener: switches mouse profile based on the active window class."""
import sys, os, fcntl, fnmatch, subprocess, tomllib

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.toml")
APPLY_PY    = os.path.join(PROJECT_DIR, "src", "apply.py")
CACHE_FILE  = "/tmp/musfocus-cache"
LOCK_FILE   = "/tmp/musfocus.lock"
WCLASS_FILE = "/tmp/FocusNotifier/wclass.txt"


def match_profile(window_class, apps):
    wclass = window_class.lower()
    for pattern, profile in apps.items():
        for part in pattern.split("|"):
            if fnmatch.fnmatch(wclass, part.strip()):
                return profile
    return "default"


def main():
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(0)

    try:
        with open(WCLASS_FILE) as f:
            window_class = f.read().strip()
    except FileNotFoundError:
        sys.exit(0)

    with open(CONFIG_PATH, "rb") as f:
        config = tomllib.load(f)

    profile = match_profile(window_class, config.get("apps", {}))

    try:
        with open(CACHE_FILE) as f:
            if f.read().strip() == profile:
                sys.exit(0)
    except FileNotFoundError:
        pass

    result = subprocess.run([sys.executable, APPLY_PY, profile])
    if result.returncode == 0:
        with open(CACHE_FILE, "w") as f:
            f.write(profile)


if __name__ == "__main__":
    main()
