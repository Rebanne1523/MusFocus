#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SYSTEMD_DIR="$HOME/.config/systemd/user"
LISTENERS_FILE="$HOME/.config/FocusNotifier/listeners.txt"
LISTENER_SHIM="$HOME/.config/musfocus-listener.sh"

echo "=== musfocus installer ==="
echo

# 0. Check & install Python dependencies.
#    (tomlkit powers the interactive menu's config editor.)
MISSING=""
python3 -c "import dbus"                    2>/dev/null || MISSING="$MISSING python-dbus"
python3 -c "import evdev"                   2>/dev/null || MISSING="$MISSING python-evdev"
python3 -c "from gi.repository import Gio"  2>/dev/null || MISSING="$MISSING python-gobject"
python3 -c "import tomlkit"                 2>/dev/null || MISSING="$MISSING python-tomlkit"
if [ -n "$MISSING" ]; then
    echo "[!] Missing Python packages:$MISSING"
    if command -v pacman &>/dev/null; then
        CMD="sudo pacman -S --needed$MISSING"
    elif command -v apt-get &>/dev/null; then
        CMD="sudo apt-get install$(echo "$MISSING" | sed 's/python-/python3-/g')"
    elif command -v dnf &>/dev/null; then
        CMD="sudo dnf install$(echo "$MISSING" | sed 's/python-/python3-/g')"
    else
        CMD=""
    fi
    if [ -n "$CMD" ]; then
        echo "    $CMD"
        read -rp "    Install these now? [Y/n] " ans
        case "$ans" in
            [Nn]*) echo "    Install them, then re-run install.sh." ; exit 1 ;;
            *)     eval "$CMD" || { echo "[!] Install failed — run it manually, then re-run." ; exit 1 ; } ;;
        esac
    else
        echo "    Install via your package manager, then re-run install.sh."
        exit 1
    fi
fi

# 1. Config
if [ ! -f "$SCRIPT_DIR/config.toml" ]; then
    cp "$SCRIPT_DIR/config.toml.example" "$SCRIPT_DIR/config.toml"
    echo "[!] Created config.toml from example."
    echo "    Edit $SCRIPT_DIR/config.toml before using musfocus."
    echo "    Run 'musfocus detect' to find your device's VID:PID and button indices."
    echo
fi

# 2. Make scripts executable
chmod +x "$SCRIPT_DIR/musfocus"
chmod +x "$SCRIPT_DIR/src/apply.py"
chmod +x "$SCRIPT_DIR/src/switcher.py"
chmod +x "$SCRIPT_DIR/src/daemon.py"

# 3. Symlink CLI to ~/.local/bin
mkdir -p "$BIN_DIR"
ln -sf "$SCRIPT_DIR/musfocus" "$BIN_DIR/musfocus"
echo "[+] CLI linked: musfocus -> $BIN_DIR/musfocus"

# 4. Migrate from previous versions
for OLD_SVC in mouse-modifier musfocus-modifier ratbag-focus-modifier; do
    if systemctl --user is-active "$OLD_SVC" &>/dev/null || \
       systemctl --user is-enabled "$OLD_SVC" &>/dev/null 2>&1; then
        echo "[~] Stopping old service: $OLD_SVC"
        systemctl --user disable --now "$OLD_SVC.service" 2>/dev/null || true
    fi
done
for OLD_BIN in ratbag-focus; do
    rm -f "$BIN_DIR/$OLD_BIN"
done
OLD_RATBAG_LISTENER="$HOME/.config/musfocus-listener.sh"
# (listener shim path hasn't changed, skip)

# 5. Install systemd service
mkdir -p "$SYSTEMD_DIR"
cat > "$SYSTEMD_DIR/musfocus-modifier.service" << EOF
[Unit]
Description=musfocus modifier daemon
After=ratbagd.service

[Service]
ExecStart=/usr/bin/python3 $SCRIPT_DIR/src/daemon.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF
echo "[+] Systemd service installed: musfocus-modifier.service"

# 6. FocusNotifier listener
if [ -d "$(dirname "$LISTENERS_FILE")" ]; then
    # Remove old listeners from previous versions
    for OLD_L in \
        "$HOME/.config/mouse-profile-switcher.sh" \
        "$HOME/.config/ratbag-focus-listener.sh"; do
        if [ -f "$LISTENERS_FILE" ] && grep -qF "$OLD_L" "$LISTENERS_FILE" 2>/dev/null; then
            echo "[~] Removing old listener: $(basename "$OLD_L")"
            grep -vF "$OLD_L" "$LISTENERS_FILE" > /tmp/.mf-listeners.tmp || true
            mv /tmp/.mf-listeners.tmp "$LISTENERS_FILE"
        fi
        rm -f "$OLD_L"
    done

    # Install shim (FocusNotifier requires a bash script)
    cat > "$LISTENER_SHIM" << EOF2
#!/usr/bin/env bash
exec /usr/bin/python3 "$SCRIPT_DIR/src/switcher.py"
EOF2
    chmod +x "$LISTENER_SHIM"

    touch "$LISTENERS_FILE"
    if ! grep -qF "$LISTENER_SHIM" "$LISTENERS_FILE"; then
        echo "$LISTENER_SHIM" >> "$LISTENERS_FILE"
        echo "[+] FocusNotifier listener registered"
    else
        echo "[=] FocusNotifier listener already registered"
    fi
else
    echo "[!] FocusNotifier not found. Install it, then add this line to listeners.txt:"
    echo "    $LISTENER_SHIM"
fi

# 7. Check udev rule for /dev/uinput
UINPUT_RULE="/etc/udev/rules.d/99-uinput-uaccess.rules"
if [ ! -f "$UINPUT_RULE" ]; then
    echo
    echo "[!] udev rule for /dev/uinput not found. Run this once:"
    echo "    echo 'KERNEL==\"uinput\", MODE=\"0660\", TAG+=\"uaccess\"' | sudo tee $UINPUT_RULE"
    echo "    sudo udevadm control --reload && sudo udevadm trigger"
fi

# 8. Enable and start service
systemctl --user daemon-reload
systemctl --user enable --now musfocus-modifier.service
echo "[+] Modifier daemon enabled and running"

echo
echo "=== Done ==="
echo "  Run 'musfocus' for the interactive menu (profiles, app mappings, device)."
echo "  Or edit $SCRIPT_DIR/config.toml directly. 'musfocus --help' lists commands."
