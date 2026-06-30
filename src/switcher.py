#!/usr/bin/env python3
"""FocusNotifier listener: records the wanted mouse profile for the active window.

It only writes the profile name to the cache file. The daemon watches that file and
swaps its software remap tables instantly (and applies DPI if it changed), so there's
no firmware commit here and switching never interrupts a drag.
"""
import sys, os, fcntl, fnmatch, tomllib

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.toml")
CACHE_FILE  = "/tmp/musfocus-cache"
LOCK_FILE   = "/tmp/musfocus.lock"
WCLASS_FILE = "/tmp/FocusNotifier/wclass.txt"


def match_profile(window_class, apps):
    wclass = window_class.lower()
    for pattern, profile in apps.items():
        for part in pattern.split("|"):
            if fnmatch.fnmatch(wclass, part.strip()):
                return profile
    return "desktop"


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

    # Atomically update the cache; the daemon picks it up and swaps instantly.
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write(profile)
    os.replace(tmp, CACHE_FILE)


if __name__ == "__main__":
    main()
