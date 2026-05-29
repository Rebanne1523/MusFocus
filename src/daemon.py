#!/usr/bin/env python3
"""
Modifier daemon: grabs the configured mouse, creates a virtual clone with the same
VID:PID (so kcminputrc acceleration settings apply), and intercepts side button clicks
while the DPI button is held to fire configurable keyboard shortcuts.
"""
import evdev
from evdev import UInput, ecodes as e
import sys, os, tomllib

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.toml")

KEY_NAME_MAP = {
    "ctrl": e.KEY_LEFTCTRL,   "leftctrl": e.KEY_LEFTCTRL,   "rightctrl": e.KEY_RIGHTCTRL,
    "shift": e.KEY_LEFTSHIFT, "leftshift": e.KEY_LEFTSHIFT, "rightshift": e.KEY_RIGHTSHIFT,
    "alt": e.KEY_LEFTALT,     "leftalt": e.KEY_LEFTALT,     "rightalt": e.KEY_RIGHTALT,
    "super": e.KEY_LEFTMETA,  "meta": e.KEY_LEFTMETA,       "leftmeta": e.KEY_LEFTMETA,
    "win": e.KEY_LEFTMETA,
    "a": e.KEY_A, "b": e.KEY_B, "c": e.KEY_C, "d": e.KEY_D, "e": e.KEY_E,
    "f": e.KEY_F, "g": e.KEY_G, "h": e.KEY_H, "i": e.KEY_I, "j": e.KEY_J,
    "k": e.KEY_K, "l": e.KEY_L, "m": e.KEY_M, "n": e.KEY_N, "o": e.KEY_O,
    "p": e.KEY_P, "q": e.KEY_Q, "r": e.KEY_R, "s": e.KEY_S, "t": e.KEY_T,
    "u": e.KEY_U, "v": e.KEY_V, "w": e.KEY_W, "x": e.KEY_X, "y": e.KEY_Y,
    "z": e.KEY_Z,
    "0": e.KEY_0, "1": e.KEY_1, "2": e.KEY_2, "3": e.KEY_3, "4": e.KEY_4,
    "5": e.KEY_5, "6": e.KEY_6, "7": e.KEY_7, "8": e.KEY_8, "9": e.KEY_9,
    "f1": e.KEY_F1,  "f2": e.KEY_F2,  "f3": e.KEY_F3,  "f4": e.KEY_F4,
    "f5": e.KEY_F5,  "f6": e.KEY_F6,  "f7": e.KEY_F7,  "f8": e.KEY_F8,
    "f9": e.KEY_F9,  "f10": e.KEY_F10, "f11": e.KEY_F11, "f12": e.KEY_F12,
    "backspace": e.KEY_BACKSPACE, "tab": e.KEY_TAB,
    "enter": e.KEY_ENTER, "return": e.KEY_ENTER,
    "esc": e.KEY_ESC, "escape": e.KEY_ESC,
    "space": e.KEY_SPACE, "delete": e.KEY_DELETE,
    "insert": e.KEY_INSERT, "home": e.KEY_HOME, "end": e.KEY_END,
    "pageup": e.KEY_PAGEUP, "pagedown": e.KEY_PAGEDOWN,
    "up": e.KEY_UP, "down": e.KEY_DOWN, "left": e.KEY_LEFT, "right": e.KEY_RIGHT,
}

BTN_NAME_MAP = {
    "BTN_LEFT":    e.BTN_LEFT,
    "BTN_RIGHT":   e.BTN_RIGHT,
    "BTN_MIDDLE":  e.BTN_MIDDLE,
    "BTN_SIDE":    e.BTN_SIDE,
    "BTN_EXTRA":   e.BTN_EXTRA,
    "BTN_FORWARD": e.BTN_FORWARD,
    "BTN_BACK":    e.BTN_BACK,
}

MODIFIER_CODES = {
    e.KEY_LEFTCTRL, e.KEY_RIGHTCTRL,
    e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT,
    e.KEY_LEFTALT, e.KEY_RIGHTALT,
    e.KEY_LEFTMETA, e.KEY_RIGHTMETA,
}


def parse_shortcut(shortcut_str):
    """Parse 'Ctrl+C' → ordered list of evdev key codes [mods..., keys...]"""
    parts = [p.strip().lower() for p in shortcut_str.split("+")]
    return [KEY_NAME_MAP[p] for p in parts if p in KEY_NAME_MAP]


def find_device(vendor_hex, product_hex):
    vendor  = int(vendor_hex, 16)
    product = int(product_hex, 16)
    for path in evdev.list_devices():
        try:
            d = evdev.InputDevice(path)
            if d.info.vendor == vendor and d.info.product == product:
                return d
            d.close()
        except Exception:
            pass
    return None


def run():
    with open(CONFIG_PATH, "rb") as f:
        config = tomllib.load(f)

    dev_cfg = config["device"]
    mod_cfg = config["modifier"]

    device = find_device(dev_cfg["vendor"], dev_cfg["product"])
    if not device:
        print(f"Device {dev_cfg['vendor']}:{dev_cfg['product']} not found.", file=sys.stderr)
        sys.exit(1)

    # The DPI button is remapped to "button:6" (BTN_FORWARD) in all profiles.
    modifier_evdev = e.BTN_FORWARD

    # Parse bindings: evdev BTN_NAME → list of key codes to press/release
    bindings = {}
    all_extra_keys = set()
    for btn_name, shortcut in mod_cfg.items():
        if btn_name == "button" or btn_name not in BTN_NAME_MAP:
            continue
        keys = parse_shortcut(shortcut)
        bindings[BTN_NAME_MAP[btn_name]] = keys
        all_extra_keys.update(keys)

    raw_caps = device.capabilities()
    # Filter EV_KEY to BTN_* range only — HIDPP firmware exports invalid key codes
    btn_codes = [c for c in raw_caps.get(e.EV_KEY, []) if 0x100 <= c <= 0x17F]
    for k in all_extra_keys:
        if k not in btn_codes:
            btn_codes.append(k)

    caps = {e.EV_KEY: btn_codes, e.EV_REL: raw_caps.get(e.EV_REL, [])}
    if e.EV_MSC in raw_caps:
        caps[e.EV_MSC] = raw_caps[e.EV_MSC]

    # Virtual device with identical VID:PID:name so kcminputrc settings apply
    ui = UInput(
        caps,
        name=device.name,
        vendor=device.info.vendor,
        product=device.info.product,
        version=device.info.version,
        bustype=device.info.bustype,
    )

    device.grab()
    print(f"Grabbed {device.path} ({device.name}), virtual device ready", flush=True)

    modifier_held = False
    active = {}  # btn_code → keys list currently held

    try:
        for event in device.read_loop():
            if event.type == e.EV_KEY:
                code, val = event.code, event.value

                if code == modifier_evdev:
                    modifier_held = (val == 1)
                    continue

                if code in bindings and (modifier_held or code in active):
                    keys = bindings[code]
                    mods  = [k for k in keys if k in MODIFIER_CODES]
                    plain = [k for k in keys if k not in MODIFIER_CODES]

                    if val == 1 and modifier_held:
                        active[code] = keys
                        for k in mods:
                            ui.write(e.EV_KEY, k, 1)
                        for k in plain:
                            ui.write(e.EV_KEY, k, 1)
                        ui.syn()
                    elif val == 0 and code in active:
                        active.pop(code)
                        for k in reversed(plain):
                            ui.write(e.EV_KEY, k, 0)
                        for k in reversed(mods):
                            ui.write(e.EV_KEY, k, 0)
                        ui.syn()
                    continue

            ui.write_event(event)
            ui.syn()

    except (KeyboardInterrupt, OSError):
        pass
    finally:
        try:
            device.ungrab()
        except Exception:
            pass
        ui.close()


if __name__ == "__main__":
    run()
