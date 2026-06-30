# MusFocus

Automatically switches your mouse button layout based on which app is active, for any mouse supported by [ratbagd/piper](https://github.com/libratbag/libratbag).

Also adds a **second modifier layer**: hold one button (like the DPI button) to give buttons second layer of functionability — similar to how holding Shift gives you capital letters, but for your mouse and every new action is customizable.

This application is tailored to help users who want extra features on their mice / looking for a linux alternative to Logitech G-Hub Software / looking for a solution for mice that only support 1 on-board profile — saving new profiles in the system rather than in the mouse's memory.

## Features

- Per-app button remapping, macros, and DPI (switches automatically when you change windows)
- **Instant** profile switching — button remaps are done in software.
- Second layer per profile: hold one button to unlock a second function layer on other buttons (different per app)
- Two switchable **assignments** per profile (e.g. one layout per in-game mode) — flip the active one from the menu; handy for a single app like Roblox that runs many different games
- Configurable trigger: any button can be the one you hold for the second layer (the DPI button by default)
- Friendly interactive menu (`musfocus`) — everything is set up here: profiles, the app each is for, buttons, shortcuts (captured by just pressing the keys)
- Works with any ratbagd-supported mouse (Logitech, Razer, SteelSeries, Roccat, etc.)
- No config files to edit — set everything up from the menu

## Requirements

- Linux with KDE Plasma (Wayland or X11) — `KDE is a MUST have` for profile switching to work properly; otherwise JUST the layered macros will work. `(other distro compatibility is being worked on)`
- [ratbagd](https://github.com/libratbag/libratbag)
- [FocusNotifier](https://github.com/Rolv-Apneseth/focus-notifier) — KWin script that fires on window changes
- Python 3.11+ with `python-dbus`, `python-evdev`, `python-gobject`, `python-tomlkit`

You don't need to install the Python packages by hand — `install.sh` does it for you.

## Installation

```bash
git clone https://github.com/Rebanne1523/MusFocus.git
cd musfocus
bash install.sh
```

`install.sh` offers to install any missing dependencies, sets up the background service, and
links the `musfocus` command. When it finishes, you're ready — just run `musfocus`.

<details>
<summary>Install the system packages yourself (optional)</summary>

```bash
# Arch / CachyOS
sudo pacman -S python-dbus python-evdev python-gobject python-tomlkit ratbagd

# Ubuntu / Debian
sudo apt install python3-dbus python3-evdev python3-gi python3-tomlkit ratbagd

# Fedora
sudo dnf install python3-dbus python3-evdev python3-gobject python3-tomlkit ratbagd
```

Then enable ratbagd: `sudo systemctl enable --now ratbagd`.
[Piper](https://github.com/libratbag/piper) is optional — a GUI to inspect your mouse.
</details>

## Getting started

Everything is done from the interactive menu. Just run:

```bash
musfocus
```

Move with ↑↓, select with Enter, go back with `q`. A typical first-time setup:

1. **Pick your mouse** — `Configuration → Device`, choose it from the list.
2. **Make a profile** — `Configuration → Profiles → + new profile`. It **first asks which app
   this profile is for** (it can *detect* the focused window, so you don't need its name), then
   you set the profile up:
   - each button — a mouse button, or a keyboard macro (**just press the keys** to capture it),
   - the **second layer** — pick a button as the *trigger* (the DPI button by default); hold it
     and click another button to fire a shortcut,
   - two **assignments** — switchable layouts you flip between right from the profile screen.

Focus the app and the profile follows automatically — instantly. Whatever app doesn't match
anything uses the built-in **`desktop`** profile. You never have to touch a config file.

## How it works

**One background daemon does everything** (`src/daemon.py`). It grabs your mouse and creates a
virtual copy with the same hardware ID (so KDE's pointer acceleration still applies), then
remaps every button **in software**, in real time — both the per-app profile and the
hold-to-activate second layer.

**Switching is instant.** FocusNotifier tells MusFocus when you change windows; it matches the
window against your app mappings and the daemon swaps its in-memory remap tables. No firmware
write, so the switch is immediate and dragging across windows never glitches.

**The mouse firmware is touched only once**, set to a fixed base so the daemon can tell which
physical button you pressed. The only thing still written to the device is **DPI**, and only
when it actually changes between profiles (in the background, and deferred while you're
mid-drag so it can't interrupt one).

## Command reference

The menu covers everything; these exist mostly for scripting:

```
musfocus            # interactive menu (default)
musfocus status     # active profile + service state
musfocus apply X    # switch to profile X right now
musfocus reload     # restart the background service
musfocus detect     # show your mouse's IDs and button indices
musfocus config     # open config.toml in your editor
```

## Manual configuration (optional)

The menu writes everything to `config.toml`, but you can edit it directly with
`musfocus config`. Inside a `[profile.X]` table:

- `dpi = N` — DPI to set when this profile activates
- `<index> = "button:N"` — make a physical button act as a mouse button
  (`1`=left, `2`=right, `3`=middle, `4`=back, `5`=front, `6`=trigger)
- `<index> = "key:Combo"` — fire a keyboard macro, e.g. `"key:Ctrl+B"`
- `<index> = "button:6"` — make that button the **trigger** for the second layer. Only one
  button can be the trigger; a profile with none simply has no second layer (so that button is
  free to be a normal key/macro).
- `[profile.X.layer2]` — the second layer; `BTN_SIDE` / `BTN_EXTRA` / `BTN_RIGHT` → a shortcut,
  fired while the trigger is held

Run `musfocus detect` to see your mouse's button indices and evdev names.

**Assignments** — every profile carries **two** switchable layouts under
`[profile.X.variants.<name>]`, with `active = "<name>"` choosing the live one. Each assignment
has its own buttons, second layer and DPI. Flip the active one from the menu
(`Profiles → your profile`, then Enter on a tab) — it applies instantly. This lets one app
(say Roblox) carry a different layout per in-game mode without a separate profile for each.

The **`desktop`** profile is special: it's the fallback used when no app matches, so it can't
be deleted and has no app of its own.

<details>
<summary>Full config.toml example</summary>

```toml
[device]
vendor  = "046d"
product = "4074"

[apps]
"*resolve*|*davinci*" = "davinci"

[profile.desktop]      # the fallback profile (used when no app matches)
dpi = 1600
3 = "button:5"      # rear thumb button  → acts as front
4 = "button:4"      # front thumb button → acts as back
5 = "button:6"      # the trigger button you hold for the second layer

[profile.desktop.layer2]
BTN_SIDE  = "Ctrl+C"   # hold trigger + back thumb  → Ctrl+C
BTN_EXTRA = "Ctrl+V"   # hold trigger + front thumb → Ctrl+V

[profile.davinci]
dpi = 800
3 = "key:Backspace"
4 = "key:Ctrl+B"
5 = "button:6"

[profile.davinci.layer2]
BTN_SIDE  = "Ctrl+B"
BTN_EXTRA = "Backspace"
```
</details>

## Adding a new mouse

In the menu, `Configuration → Device` to pick it, then create your profiles. The trigger that
activates the second layer is the button set to `"button:6"` (the DPI button on most mice). If
your mouse isn't in ratbagd's database, per-app switching won't work, but the second layer
still works for any USB mouse with extra buttons.

## Uninstall

```bash
bash uninstall.sh
```

Your `config.toml` is preserved. Delete the `~/musfocus/` folder to remove everything.
