# MusFocus

Automatically switches your mouse button layout based on which app is active, for any mouse supported by [ratbagd/piper](https://github.com/libratbag/libratbag).

Also adds a **modifier layer**: hold one button (like the DPI button) to turn other buttons into keyboard shortcuts — similar to how holding Shift gives you capital letters, but for your mouse.

## Features

- Per-app button remapping, macros, and DPI (switches automatically when you change windows)
- Modifier layer: hold one button to unlock a second set of actions on other buttons
- Works with any ratbagd-supported mouse (Logitech, Razer, SteelSeries, Roccat, etc.)
- Near-instant switching (~30ms) with background hardware write
- One config file — no Python knowledge needed

## Requirements

- Linux with KDE Plasma (Wayland or X11) `KDE is a MUST have` for the profile switching to work properly, otherwise JUST the layered macros will work.
- [ratbagd](https://github.com/libratbag/libratbag) — `sudo systemctl enable --now ratbagd`
- [FocusNotifier](https://github.com/Rolv-Apneseth/focus-notifier) — KWin script that fires on window changes
- Python 3.11+ with `python-dbus`, `python-evdev`, `python-gobject`

On Arch/CachyOS:
```bash
sudo pacman -S python-dbus python-evdev python-gobject ratbagd
```

On Ubuntu/Debian:
```bash
sudo apt install python3-dbus python3-evdev python3-gi ratbagd
```

On Fedora:
```bash
sudo dnf install python3-dbus python3-evdev python3-gobject ratbagd
```

[Piper](https://github.com/libratbag/piper) is optional but useful to visually inspect your mouse's button layout and verify that profiles are applying correctly.

## Installation

```bash
git clone https://github.com/Rebanne1523/MusFocus.git
cd musfocus
bash install.sh
```

The installer checks for missing dependencies and tells you what to install if anything is missing.

Then open the config:
```bash
musfocus config
```

## Commands

```
musfocus config              # open config.toml in your editor
musfocus status              # current profile, service state, device info
musfocus list                # show all profiles, app mappings, shortcuts
musfocus apply <profile>     # apply a profile right now (e.g. "default")
musfocus reload              # restart background service after config changes
musfocus detect              # find your mouse's VID:PID and button indices
musfocus detect --window     # show the current window's class name
```

## Configuration

All configuration lives in `config.toml` inside the project folder. Open it with:
```bash
musfocus config
```
Once you are happy with your configuration press `Ctrl+S` to save and the `Ctrl+X` to exit.


### Step 1 — Find your mouse's IDs

```bash
musfocus detect
```

Look at the **Input device VID:PIDs** section (not lsusb — for wireless mice, lsusb shows the receiver's ID, not the mouse's). Example:
```
046d:4074  Logitech G305
```

Put those values in config.toml:
```toml
[device]
vendor  = "046d"
product = "4074"
```

### Step 2 — Find button indices

The same `detect` command prints the button indices ratbagd uses for your mouse, along with the evdev name for each:
```
    [0]  button:1   →  BTN_LEFT        (left click)
    [1]  button:2   →  BTN_RIGHT       (right click)
    [2]  button:3   →  BTN_MIDDLE      (middle)
    [3]  button:5   →  BTN_EXTRA       (forward (extra))
    [4]  button:4   →  BTN_SIDE        (back (side))
    [5]  button:6   →  BTN_FORWARD     (modifier trigger)

```

The number in brackets (0, 1, 3, 4, 5...) is the **button index** you use in profiles. The evdev name is what you use in the `[modifier]` section, the number next to "button" modifier button that you will use for the layering modifier function.

### Step 3 — Add app profiles

Focus the app you want a custom layout for, then run:
```bash
musfocus detect --window
```

This shows the window class name, for example `resolve`. Use it in `config.toml`:
```toml
[apps]
"*resolve*" = "davinci"
```

Use `*` as wildcard. Separate multiple patterns with `|`:
```toml
"*resolve*|*davinci*" = "davinci"
```

The window class is usually the app's executable name in lowercase. Run `musfocus detect --window` while the app is focused to get the exact value.

### Understanding profile actions

Each line in a profile maps a button index to an action:

```toml
[profile.davinci]
dpi = 800
3 = "key:Backspace"    # button 3 fires Backspace
4 = "key:Ctrl+B"       # button 4 fires Ctrl+B
5 = "button:6"         # button 5 stays available for the modifier layer
```

**`dpi = N`** — sets the active DPI when this profile activates. Run `musfocus detect` to see the allowed DPI values for your mouse.

**`key:Shortcut`** — fires a keyboard shortcut:
- `"key:Backspace"`
- `"key:Ctrl+B"`, `"key:Ctrl+Shift+Z"`, `"key:Super+F"`

**`button:N`** — remaps the button to act as a different mouse button:
- `button:1` = left click
- `button:2` = right click
- `button:3` = middle click
- `button:4` = back
- `button:5` = forward
- `button:6` = required for the modifier button (see below)

### The modifier layer

Think of it like a second layer on your mouse, activated by holding one button. While you hold the modifier button, other buttons fire keyboard shortcuts instead of their normal actions. Release it and everything goes back to normal — similar to how Shift works on a keyboard.

```toml
[modifier]
button    = 5           # button INDEX to hold to activate the layer
BTN_SIDE  = "Ctrl+C"   # while holding: side button fires Ctrl+C
BTN_EXTRA = "Ctrl+V"   # while holding: extra button fires Ctrl+V
BTN_RIGHT = "Super+F"  # while holding: right click fires Super+F
```

`button = 5` is the index of the button you hold. The names (`BTN_SIDE`, `BTN_EXTRA`, `BTN_RIGHT`) are the evdev names shown by `musfocus detect`.

**One required step:** the modifier button must be set to `"button:6"` or the corresponding button in every profile. This makes the button's press visible to the background service — without this, some mice handle the button entirely in firmware and the OS never receives the event.

So if your modifier button has index 5, every profile needs this line:
```toml
5 = "button:6"
```

### Full example

```toml
[device]
vendor  = "046d"
product = "4074"

[modifier]
button    = 5
BTN_SIDE  = "Ctrl+C"
BTN_EXTRA = "Ctrl+V"
BTN_RIGHT = "Super+F"

[apps]
"*resolve*|*davinci*" = "davinci"

[profile.default]
dpi = 1600
3 = "button:5"      # physical back button -> forward
4 = "button:4"      # physical forward button -> back
5 = "button:6"      # modifier button (required in every profile)

[profile.davinci]
dpi = 800
3 = "key:Backspace"
4 = "key:Ctrl+B"
5 = "button:6"
```

## How It Works

**Profile switching** — FocusNotifier notifies MusFocus whenever you switch windows. It matches the window class against the `[apps]` patterns and calls the ratbagd DBus API to rewrite button mappings and DPI in a single session. A cache file prevents redundant writes (and mouse drag interruptions).

**Modifier daemon** — A background service (`src/daemon.py`) grabs your mouse and creates a virtual copy with the same hardware ID, so KDE's pointer acceleration settings still apply. It intercepts events in real time: when the modifier button is held, configured buttons fire keyboard shortcuts; everything else passes through unchanged.

## Adding a New Mouse

1. Run `musfocus detect` to find the VID:PID and button indices
2. Update `[device]`, the profile button indices, and `[modifier].button` in config.toml
3. Run `musfocus reload`

If your mouse is not in ratbagd's device database, the per-app profile switching won't work — but the modifier layer still works for any USB mouse with side buttons. You just need its VID:PID from `musfocus detect`.

## Uninstall

```bash
bash uninstall.sh
```

Your `~/musfocus/config.toml` is preserved. Delete the `~/musfocus/` folder to fully remove everything.
