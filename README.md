# MusFocus

Automatically switches your mouse button layout based on which app is active, for any mouse supported by [ratbagd/piper](https://github.com/libratbag/libratbag).

Also adds a **modifier layer**: hold one button (like the DPI button) to turn other buttons into keyboard shortcuts — similar to how holding Shift gives you capital letters, but for your mouse.

## Features

- Per-app button remapping, macros, and DPI (switches automatically when you change windows)
- **Instant** profile switching — button remaps are done in software, so there's no firmware write to wait for and dragging across windows never glitches
- Second layer per profile: hold one button to unlock a different set of actions on other buttons (different per app)
- Friendly interactive menu (`musfocus`) — add/edit profiles, app mappings, shortcuts, and capture key combos by just pressing them
- Works with any ratbagd-supported mouse (Logitech, Razer, SteelSeries, Roccat, etc.)
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

Then just run:
```bash
musfocus
```
This opens an interactive menu where you can set up everything — profiles, the buttons
on each profile, which app uses which profile, and the second-layer shortcuts. Optional
packages for the menu: `python-tomlkit` (so edits keep your config comments).

## Commands

The interactive menu (`musfocus` with no arguments) is the easy way in. These subcommands
also exist for scripting:

```
musfocus                     # interactive menu (profiles, mappings, shortcuts, device)
musfocus status              # current profile, service state, device info
musfocus list                # show all profiles, app mappings, shortcuts
musfocus apply <profile>     # switch to a profile right now (e.g. "default")
musfocus reload              # restart background service after config changes
musfocus detect              # find your mouse's VID:PID and button indices
musfocus detect --window     # show the current window's class name
musfocus config              # open config.toml in your editor
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

### The second layer (per profile)

Think of it like a second layer on your mouse, activated by holding one button (the
trigger). While you hold it, other buttons fire keyboard shortcuts instead of their
normal actions. Release it and everything goes back to normal — like Shift on a keyboard.

The second layer is **per profile**, so the same hold-and-click can do different things in
different apps. It lives in a `[profile.X.layer2]` table:

```toml
[profile.davinci.layer2]
BTN_SIDE  = "Ctrl+B"      # while holding the trigger: side button → Ctrl+B
BTN_EXTRA = "Backspace"   # while holding the trigger: extra button → Backspace
```

The names (`BTN_SIDE`, `BTN_EXTRA`, `BTN_RIGHT`) are the evdev names shown by
`musfocus detect`. The easiest way to set these is the interactive menu
(`musfocus` → Profiles → your profile → Second layer), which lets you **capture** a
shortcut by just pressing the keys.

**The trigger button:** one button in each profile must be set to `"button:6"`. Holding
that button is what activates the second layer. Without it, some mice handle the button
entirely in firmware and the OS never sees the press.

```toml
5 = "button:6"    # the DPI button (index 5) is the trigger
```

A legacy global `[modifier]` table is still supported as a fallback for any profile that
doesn't define its own `[profile.X.layer2]`.

### Full example

```toml
[device]
vendor  = "046d"
product = "4074"

[apps]
"*resolve*|*davinci*" = "davinci"

[profile.default]
dpi = 1600
3 = "button:5"      # physical back button -> forward
4 = "button:4"      # physical forward button -> back
5 = "button:6"      # trigger button (required in every profile)

[profile.default.layer2]
BTN_SIDE  = "Ctrl+C"   # hold trigger + side  → Ctrl+C
BTN_EXTRA = "Ctrl+V"   # hold trigger + extra → Ctrl+V

[profile.davinci]
dpi = 800
3 = "key:Backspace"
4 = "key:Ctrl+B"
5 = "button:6"

[profile.davinci.layer2]
BTN_SIDE  = "Ctrl+B"
BTN_EXTRA = "Backspace"
```

## How It Works

**One background daemon does everything** (`src/daemon.py`). It grabs your mouse and creates
a virtual copy with the same hardware ID (so KDE's pointer acceleration still applies), then
remaps every button **in software** in real time — both the per-app profile and the
hold-to-activate second layer.

**Profile switching is instant.** FocusNotifier notifies MusFocus on window changes; it
matches the window class against `[apps]` and writes the profile name to a small cache file.
The daemon watches that file and swaps its in-memory remap tables — no firmware write, so the
switch is immediate and dragging across windows never glitches.

**The firmware is set once** to a fixed "identity" base (button index *i* emits button *i+1*)
so the daemon can tell which physical button you pressed. The only thing still written to the
device is **DPI**, and only when it actually changes between profiles (done in the background,
and deferred while you're mid-drag).

## Adding a New Mouse

1. Run `musfocus detect` to find the VID:PID and button indices
2. In the menu (`musfocus` → Configuration → Device) pick your mouse, then set up profiles
3. Run `musfocus reload`

The trigger that activates the second layer is the button mapped to `"button:6"` (the DPI button on most mice). If your mouse is not in ratbagd's device database, per-app switching won't work, but the second layer still works for any USB mouse with extra buttons — you just need its VID:PID from `musfocus detect`.

## Uninstall

```bash
bash uninstall.sh
```

Your `~/musfocus/config.toml` is preserved. Delete the `~/musfocus/` folder to fully remove everything.
