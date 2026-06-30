#!/usr/bin/env python3
"""
musfocus daemon: grabs the configured mouse, creates a virtual clone with the same
VID:PID (so kcminputrc acceleration settings apply), and does ALL button remapping in
software — both the per-app profile (first layer) and the hold-to-activate shortcuts
(second layer). Because remapping is software, switching profiles is instant: no
ratbagd firmware commit is needed (only DPI, when it actually changes, still uses it).

The mouse firmware is set once to a fixed "identity" base (button index i emits button
i+1) so the daemon can tell which physical button was pressed; everything else is then
remapped here.
"""
import evdev
from evdev import UInput, ecodes as e
import sys, os, tomllib, subprocess, threading, select

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_DIR, "config.toml")
APPLY_PY    = os.path.join(PROJECT_DIR, "src", "apply.py")
CACHE_FILE  = "/tmp/musfocus-cache"

# Buttons whose hold means "a drag may be in progress" → defer the (rare) DPI commit.
DRAG_BTNS = {e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE}

# ratbag button number → evdev code. The fixed base maps physical index i to button i+1.
BTN_NUM_TO_EVDEV = {
    1: e.BTN_LEFT, 2: e.BTN_RIGHT, 3: e.BTN_MIDDLE, 4: e.BTN_SIDE,
    5: e.BTN_EXTRA, 6: e.BTN_FORWARD, 7: e.BTN_BACK, 8: e.BTN_TASK,
}
# The trigger (modifier) is button 6 → BTN_FORWARD. Holding it activates the 2nd layer.
MODIFIER_EVDEV = e.BTN_FORWARD

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


def base_code(index):
    """Evdev code a physical button emits under the fixed identity base."""
    return BTN_NUM_TO_EVDEV.get(index + 1)


def parse_button_action(action):
    """Profile action string → list of evdev codes to emit, or None to pass through.

    'button:N' → [evdev code for button N]   (None for the trigger, button:6)
    'key:Combo' → [key codes]
    """
    action = str(action)
    if action.startswith("button:"):
        try:
            n = int(action.split(":", 1)[1])
        except ValueError:
            return None
        if n == 6:                       # the modifier trigger isn't a first-layer emit
            return None
        code = BTN_NUM_TO_EVDEV.get(n)
        return [code] if code is not None else None
    if action.startswith("key:"):
        return parse_shortcut(action.split(":", 1)[1])
    return None


def build_first_layer(pcfg):
    """Profile table → {source evdev code: [emit codes]} (identity remaps skipped)."""
    out = {}
    for k, v in pcfg.items():
        if k in ("dpi", "layer2"):
            continue
        try:
            idx = int(k)
        except (ValueError, TypeError):
            continue
        src = base_code(idx)
        codes = parse_button_action(v)
        if src is None or not codes:
            continue
        if codes == [src]:               # identity → just pass through
            continue
        out[src] = codes
    return out


def build_second_layer(section):
    """Layer-2 table → {source evdev code: [key codes]}."""
    out = {}
    for name, shortcut in section.items():
        if name in BTN_NAME_MAP:
            out[BTN_NAME_MAP[name]] = parse_shortcut(shortcut)
    return out


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
    profiles = config.get("profile", {})
    global_mod = config.get("modifier", {})   # fallback 2nd layer for profiles w/o layer2

    device = find_device(dev_cfg["vendor"], dev_cfg["product"])
    if not device:
        print(f"Device {dev_cfg['vendor']}:{dev_cfg['product']} not found.", file=sys.stderr)
        sys.exit(1)

    # Pre-build software remap tables for every profile (instant to swap between).
    default_second = build_second_layer(global_mod)
    first_layers  = {n: build_first_layer(p) for n, p in profiles.items()}
    second_layers = {n: build_second_layer(p.get("layer2", global_mod))
                     for n, p in profiles.items()}
    profile_dpi   = {n: p.get("dpi") for n, p in profiles.items()}

    # Collect every key code any layer can emit so the virtual device can carry them.
    all_emit_keys = set()
    for table in list(first_layers.values()) + list(second_layers.values()) + [default_second]:
        for codes in table.values():
            all_emit_keys.update(codes)

    raw_caps = device.capabilities()
    # Standard keyboard keys (1-127) and mouse buttons (0x100-0x17F); HIDPP firmware
    # exports out-of-range codes that would make uinput fail.
    VALID_KEY_CODES = set(range(1, 128)) | set(range(0x100, 0x180))
    btn_codes = [c for c in raw_caps.get(e.EV_KEY, []) if c in VALID_KEY_CODES]
    for k in all_emit_keys:
        if k not in btn_codes:
            btn_codes.append(k)

    caps = {e.EV_KEY: btn_codes, e.EV_REL: raw_caps.get(e.EV_REL, [])}
    if e.EV_MSC in raw_caps:
        caps[e.EV_MSC] = raw_caps[e.EV_MSC]

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

    # ── helpers ──────────────────────────────────────────────────────────────
    def press(codes):
        for k in [c for c in codes if c in MODIFIER_CODES]:
            ui.write(e.EV_KEY, k, 1)
        for k in [c for c in codes if c not in MODIFIER_CODES]:
            ui.write(e.EV_KEY, k, 1)
        ui.syn()

    def release(codes):
        for k in reversed([c for c in codes if c not in MODIFIER_CODES]):
            ui.write(e.EV_KEY, k, 0)
        for k in reversed([c for c in codes if c in MODIFIER_CODES]):
            ui.write(e.EV_KEY, k, 0)
        ui.syn()

    def run_apply(*args):
        def work():
            try:
                subprocess.run([sys.executable, APPLY_PY, *args], timeout=15)
            except subprocess.TimeoutExpired:
                pass
        threading.Thread(target=work, daemon=True).start()

    modifier_held = False
    active = {}      # source evdev code → emitted codes currently held down
    held = set()     # drag buttons currently down

    state = {"name": None, "first": {}, "second": default_second, "dpi": None}

    def maybe_apply_dpi():
        target = profile_dpi.get(state["name"])
        if target is None or held:        # no DPI set, or defer while dragging
            return
        if state["dpi"] != target:
            state["dpi"] = target
            run_apply("dpi", str(target))

    def load_active():
        try:
            with open(CACHE_FILE) as f:
                name = f.read().strip()
        except OSError:
            name = ""
        if name not in profiles:
            name = "default" if "default" in profiles else name
        state["name"]   = name
        state["first"]  = first_layers.get(name, {})
        state["second"] = second_layers.get(name, default_second)
        maybe_apply_dpi()

    # Set the fixed firmware base once (so physical buttons emit known codes), then
    # load the active profile's software tables.
    run_apply("base")
    load_active()

    def cache_mtime():
        try:
            return os.stat(CACHE_FILE).st_mtime
        except OSError:
            return 0.0
    last_mtime = cache_mtime()

    try:
        while True:
            r, _, _ = select.select([device.fd], [], [], 0.1)

            # Profile changed? Swap software tables instantly (no firmware commit).
            m = cache_mtime()
            if m != last_mtime:
                last_mtime = m
                load_active()

            if not r:
                continue
            try:
                events = list(device.read())
            except BlockingIOError:
                continue

            for event in events:
                if event.type != e.EV_KEY:
                    ui.write_event(event)
                    ui.syn()
                    continue

                code, val = event.code, event.value

                if code == MODIFIER_EVDEV:
                    # The trigger autorepeats (val==2) while held; only val==0 releases.
                    modifier_held = (val != 0)
                    continue

                # Release an in-flight remap, even if the profile changed meanwhile.
                if val == 0 and code in active:
                    release(active.pop(code))
                    if code in DRAG_BTNS:
                        held.discard(code)
                        if not held:
                            maybe_apply_dpi()
                    continue
                # Swallow autorepeat of a button whose remap is already held.
                if code in active:
                    continue

                # Pick the effective binding: 2nd layer wins while the trigger is held.
                binding = None
                if modifier_held and code in state["second"]:
                    binding = state["second"][code]
                elif code in state["first"]:
                    binding = state["first"][code]

                if binding is not None:
                    if val == 1:
                        active[code] = binding
                        press(binding)
                        if code in DRAG_BTNS:
                            held.add(code)
                    continue

                # Pass through unmapped buttons; track drags to defer DPI commits.
                if code in DRAG_BTNS:
                    if val == 1:
                        held.add(code)
                    elif val == 0:
                        held.discard(code)
                        if not held:
                            maybe_apply_dpi()
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
