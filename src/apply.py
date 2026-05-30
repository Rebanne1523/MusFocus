#!/usr/bin/env python3
"""Applies a ratbag profile from config.toml to the connected mouse via DBus."""
import dbus, sys, os, subprocess, tomllib

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.toml")

# Linux evdev scancodes used by ratbagd macros
KEY_MAP = {
    "esc": 1, "escape": 1, "1": 2, "2": 3, "3": 4, "4": 5, "5": 6,
    "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
    "backspace": 14, "tab": 15, "enter": 28, "return": 28,
    "ctrl": 29, "leftctrl": 29, "rightctrl": 97,
    "shift": 42, "leftshift": 42, "rightshift": 54,
    "alt": 56, "leftalt": 56, "rightalt": 100,
    "super": 125, "meta": 125, "leftmeta": 125, "win": 125,
    "space": 57,
    "a": 30, "b": 48, "c": 46, "d": 32, "e": 18, "f": 33, "g": 34,
    "h": 35, "i": 23, "j": 36, "k": 37, "l": 38, "m": 50, "n": 49,
    "o": 24, "p": 25, "q": 16, "r": 19, "s": 31, "t": 20, "u": 22,
    "v": 47, "w": 17, "x": 45, "y": 21, "z": 44,
    "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64,
    "f7": 65, "f8": 66, "f9": 67, "f10": 68, "f11": 87, "f12": 88,
    "delete": 111, "insert": 110, "home": 102, "end": 107,
    "pageup": 104, "pagedown": 109,
    "up": 103, "down": 108, "left": 105, "right": 106,
}

MODIFIER_KEYS = {
    "ctrl", "leftctrl", "rightctrl",
    "shift", "leftshift", "rightshift",
    "alt", "leftalt", "rightalt",
    "super", "meta", "leftmeta", "win",
}


def parse_key_combo(combo_str):
    """Parse 'Ctrl+B' → ratbagd macro event list [(event_type, scancode), ...]"""
    parts = [p.strip().lower() for p in combo_str.split("+")]
    mods = [p for p in parts if p in MODIFIER_KEYS]
    keys = [p for p in parts if p not in MODIFIER_KEYS]

    events = []
    for m in mods:
        events.append((1, KEY_MAP[m]))
    for k in keys:
        events.append((1, KEY_MAP[k]))
    for k in reversed(keys):
        events.append((2, KEY_MAP[k]))
    for m in reversed(mods):
        events.append((2, KEY_MAP[m]))
    return events


def parse_action(action_str):
    """Parse 'button:5' or 'key:Ctrl+B' → (kind, data)"""
    if action_str.startswith("button:"):
        return ("button", int(action_str.split(":", 1)[1]))
    elif action_str.startswith("key:"):
        return ("macro", parse_key_combo(action_str.split(":", 1)[1]))
    else:
        raise ValueError(f"Unknown action format: {action_str!r}")


def button_mapping(n):
    return dbus.Struct(
        (dbus.UInt32(1), dbus.UInt32(n, variant_level=1)),
        signature="uv",
    )


def macro_mapping(keys):
    return dbus.Struct(
        (
            dbus.UInt32(4),
            dbus.Array(
                [(dbus.UInt32(t), dbus.UInt32(k)) for t, k in keys],
                signature="(uu)",
                variant_level=1,
            ),
        ),
        signature="uv",
    )


def set_dpi(bus, hidraw, dpi):
    # ratbagd's Resolution property has DBus type 'v' (variant), so we need
    # to send v{v{u}} — the Properties.Set 'v' slot contains our value of type 'v'.
    from gi.repository import Gio, GLib
    conn = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    profile_obj = bus.get_object(
        "org.freedesktop.ratbag1",
        f"/org/freedesktop/ratbag1/profile/{hidraw}/p0",
    )
    profile_props = dbus.Interface(profile_obj, "org.freedesktop.DBus.Properties")
    resolutions = profile_props.Get("org.freedesktop.ratbag1.Profile", "Resolutions")
    for res_path in resolutions:
        res_obj = bus.get_object("org.freedesktop.ratbag1", str(res_path))
        res_props = dbus.Interface(res_obj, "org.freedesktop.DBus.Properties")
        if res_props.Get("org.freedesktop.ratbag1.Resolution", "IsActive"):
            conn.call_sync(
                "org.freedesktop.ratbag1", str(res_path),
                "org.freedesktop.DBus.Properties", "Set",
                GLib.Variant("(ssv)", (
                    "org.freedesktop.ratbag1.Resolution", "Resolution",
                    GLib.Variant("v", GLib.Variant("u", dpi)),
                )),
                None, Gio.DBusCallFlags.NONE, -1, None,
            )
            return


def apply_profile(name, config):
    profiles = config.get("profile", {})
    profile = profiles.get(name)
    if profile is None:
        print(f"Unknown profile: {name!r}", file=sys.stderr)
        print(f"Available: {', '.join(profiles)}", file=sys.stderr)
        sys.exit(1)

    bus = dbus.SystemBus()
    mgr = dbus.Interface(
        bus.get_object("org.freedesktop.ratbag1", "/org/freedesktop/ratbag1"),
        "org.freedesktop.DBus.Properties",
    )
    devices = mgr.Get("org.freedesktop.ratbag1.Manager", "Devices")
    if not devices:
        print("No ratbagd devices found.", file=sys.stderr)
        sys.exit(0)

    hidraw = str(devices[0]).split("/")[-1]

    for btn_idx_str, action_str in profile.items():
        if btn_idx_str == "dpi":
            continue
        btn_idx = int(btn_idx_str)
        kind, data = parse_action(action_str)
        obj = bus.get_object(
            "org.freedesktop.ratbag1",
            f"/org/freedesktop/ratbag1/button/{hidraw}/p0/b{btn_idx}",
        )
        props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
        mapping = button_mapping(data) if kind == "button" else macro_mapping(data)
        props.Set("org.freedesktop.ratbag1.Button", "Mapping", mapping)

    if "dpi" in profile:
        set_dpi(bus, hidraw, int(profile["dpi"]))

    dev_path = f"/org/freedesktop/ratbag1/device/{hidraw}"
    commit_cmd = (
        f"import dbus; bus=dbus.SystemBus(); "
        f"dbus.Interface(bus.get_object('org.freedesktop.ratbag1','{dev_path}'),"
        f"'org.freedesktop.ratbag1.Device').Commit()"
    )
    subprocess.Popen(
        [sys.executable, "-c", commit_cmd],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <profile>", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH, "rb") as f:
        config = tomllib.load(f)
    apply_profile(sys.argv[1], config)
