# MusFocus

Automatically switches your mouse button layout based on which app is active, for any mouse supported by [ratbagd/piper](https://github.com/libratbag/libratbag).

Also adds a **modifier layer**: hold one button (like the DPI button) to turn other buttons into keyboard shortcuts — similar to how holding Shift gives you capital letters, but for your mouse.

## Features

- Per-app button remapping and macros (switches automatically when you change windows)
- Modifier layer: hold one button to unlock a second set of actions on other buttons
- Works with any ratbagd-supported mouse (Logitech, Razer, SteelSeries, Roccat, etc.)
- Near-instant switching (~30ms) with background hardware write
- One config file — no Python knowledge needed

## Requirements

- Linux with KDE Plasma (Wayland or X11)
- [ratbagd](https://github.com/libratbag/libratbag) — `sudo systemctl enable --now ratbagd`
- [FocusNotifier](https://github.com/Rolv-Apneseth/focus-notifier) — KWin script that fires on window changes
- Python 3.11+
- `python-dbus` and `python-evdev`

On Arch/CachyOS:
```bash
sudo pacman -S python-dbus python-evdev ratbagd
```

[Piper](https://github.com/libratbag/piper) is optional but useful to visually inspect your mouse's button layout and verify that profiles are applying correctly.

## Installation

```bash
git clone https://github.com/yourname/musfocus
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

### Step 1 — Find your mouse's IDs

```bash
musfocus detect
```

Look at the **Input device VID:PIDs** section (not lsusb — wireless mice show the receiver's ID there, not the mouse's). Example:
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

The same `detect` command also prints the button indices ratbagd uses for your mouse:
```
Button 0: action = button 1   <- left click
Button 1: action = button 2   <- right click
Button 3: action = button 5   <- back side button
Button 4: action = button 4   <- forward side button
Button 5: action = button 6   <- DPI button
```
The number at the start of each line (0, 1, 3, 4, 5...) is the index you use in profiles.

### Step 3 — Add app profiles

Focus the app you want a custom layout for, then:
```bash
musfocus detect --window
```
This shows the window class name, for example `resolve`. Use it in config.toml:
```toml
[apps]
"*resolve*" = "davinci"
```
Use `*` as wildcard. Separate multiple patterns with `|`:
```toml
"*resolve*|*davinci*" = "davinci"
```

The window class is usually the app's executable name in lowercase. If you're unsure, run `musfocus detect --window` while the app is focused and use whatever it shows.

### Understanding profile actions

Each line in a profile maps a button index to an action:

```toml
[profile.davinci]
3 = "key:Backspace"    # button 3 fires Backspace
4 = "key:Ctrl+B"       # button 4 fires Ctrl+B
5 = "button:6"         # button 5 stays available for the modifier layer
```

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

Think of it like a second layer on your mouse, activated by holding one button. While you hold the modifier button, other buttons fire keyboard shortcuts instead of their normal actions. Release it and everything goes back to normal.

```toml
[modifier]
button    = 5          # the button INDEX you hold to activate the layer
BTN_SIDE  = "Ctrl+C"  # while holding: side button fires Ctrl+C
BTN_EXTRA = "Ctrl+V"  # while holding: extra button fires Ctrl+V
BTN_RIGHT = "Super+F" # while holding: right click fires Super+F
```

**One required step:** the modifier button must be set to `"button:6"` in every profile. This is what makes the button's press visible to the background service — without this remapping, some mice handle the button entirely in firmware and the OS never receives the event.

So if your modifier button has index 5, every profile needs this line:
```toml
5 = "button:6"
```

The button names (`BTN_SIDE`, `BTN_EXTRA`, `BTN_RIGHT`) are Linux kernel names. Run `musfocus detect` to see which physical buttons map to which names.

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
3 = "button:5"      # physical back button -> forward
4 = "button:4"      # physical forward button -> back
5 = "button:6"      # modifier button (required in every profile)

[profile.davinci]
3 = "key:Backspace"
4 = "key:Ctrl+B"
5 = "button:6"
```

## How It Works

**Profile switching** — FocusNotifier notifies MusFocus whenever you switch windows. It matches the window class against the `[apps]` patterns and calls the ratbagd DBus API to rewrite button mappings in a single session. A cache file prevents redundant writes (and mouse drag interruptions).

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
