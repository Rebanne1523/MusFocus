# ratbag-focus

Per-app mouse profile switcher for any mouse supported by [ratbagd/piper](https://github.com/libratbag/libratbag).

Automatically applies button remaps and macros based on the active window. Also supports a modifier button that turns side buttons into configurable keyboard shortcuts while held.

## Features

- Switches mouse button profiles automatically when you change apps
- Configurable keyboard shortcut modifier (hold one button to fire shortcuts with others)
- Works with any mouse ratbagd supports (Logitech, Razer, SteelSeries, Roccat, etc.)
- Near-instant switching (~30ms) with background NVM commit
- Single TOML config file — no need to edit Python

## Requirements

- Linux with KDE Plasma (Wayland or X11)
- [ratbagd](https://github.com/libratbag/libratbag) (`sudo systemctl enable --now ratbagd`)
- [FocusNotifier](https://github.com/Rolv-Apneseth/focus-notifier) (KWin script for window class events)
- Python 3.11+
- `python-dbus` and `python-evdev` packages

On Arch/CachyOS:
```
sudo pacman -S python-dbus python-evdev ratbagd
```

## Installation

```bash
git clone https://github.com/yourname/ratbag-focus
cd ratbag-focus
cp config.toml.example config.toml
# Edit config.toml for your mouse (see Configuration below)
bash install.sh
```

## Configuration

All configuration lives in `config.toml` in the project directory.

### 1. Find your mouse's VID:PID

```bash
ratbag-focus detect
```

Look for your mouse in the `lsusb` output. Example: `ID 046d:4074` → vendor `046d`, product `4074`.

### 2. Find button indices

```bash
ratbag-focus detect
```

This also runs `ratbagctl <device> profile 0 button list` for every ratbagd-detected device and shows the button indices.

### 3. Find window classes for app mappings

Focus the app you want to profile, then:

```bash
ratbag-focus detect --window
```

### 4. Edit config.toml

```toml
[device]
vendor  = "046d"
product = "4074"

[modifier]
button = 5          # ratbagd button index used as modifier
BTN_SIDE  = "Ctrl+C"
BTN_EXTRA = "Ctrl+V"
BTN_RIGHT = "Super+F"

[apps]
"*resolve*|*davinci*" = "davinci"

[profile.default]
3 = "button:5"      # remap to forward
4 = "button:4"      # remap to back
5 = "button:6"      # DPI button → BTN_FORWARD (required for modifier)

[profile.davinci]
3 = "key:Backspace"
4 = "key:Ctrl+B"
5 = "button:6"
```

**Action format:**
- `"button:N"` — send mouse button event (4=back, 5=forward, 6=BTN_FORWARD)
- `"key:Shortcut"` — fire a keyboard macro (e.g. `"key:Ctrl+B"`, `"key:Backspace"`, `"key:Super+F"`)

**Modifier shortcuts** use evdev button names: `BTN_LEFT`, `BTN_RIGHT`, `BTN_MIDDLE`, `BTN_SIDE`, `BTN_EXTRA`, `BTN_FORWARD`, `BTN_BACK`.

The modifier button must be remapped to `"button:6"` in all profiles so the daemon can detect it as `BTN_FORWARD`.

### Adding a new app profile

1. Focus the app, run `ratbag-focus detect --window` to get its window class
2. Add an entry under `[apps]` and a new `[profile.myprofile]` section in `config.toml`
3. Run `ratbag-focus reload`

## Commands

```
ratbag-focus status              # current profile, daemon state, device info
ratbag-focus list                # all profiles, app mappings, shortcuts
ratbag-focus apply <profile>     # apply a profile immediately
ratbag-focus reload              # restart modifier daemon, clear profile cache
ratbag-focus detect              # show ratbagd devices, button indices, lsusb output
ratbag-focus detect --window     # show current window class
```

## How It Works

- **Profile switcher**: FocusNotifier fires a listener script on every window focus change. The listener reads the window class, matches it against `[apps]` patterns in `config.toml`, and calls `src/apply.py` to set button mappings via the ratbagd DBus API in a single session (avoids the ~2.4s wake penalty from separate ratbagctl calls). A profile cache prevents redundant applies.

- **Modifier daemon**: Grabs the real mouse device via evdev and creates a virtual clone with the same VID:PID and name, so existing libinput acceleration settings (kcminputrc) apply automatically. Intercepts the DPI button and transforms side button clicks into keyboard shortcuts while it's held. All other events are forwarded unchanged.

## Adding a New Mouse

1. Run `ratbag-focus detect` to find VID:PID and button indices
2. Update `[device]`, `[modifier].button`, and `[profile.*]` in `config.toml`
3. Run `ratbag-focus reload`

If your mouse isn't detected by ratbagd (not in the [device database](https://github.com/libratbag/libratbag/tree/master/data/devices)), the profile switcher won't work, but the modifier daemon will still function for any standard HID mouse — just set the correct VID:PID.

## Uninstall

```bash
bash uninstall.sh
```

Your `config.toml` is preserved. Delete the project directory for a full removal.
