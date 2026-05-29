#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SYSTEMD_DIR="$HOME/.config/systemd/user"
LISTENERS_FILE="$HOME/.config/FocusNotifier/listeners.txt"
LISTENER_SHIM="$HOME/.config/ratbag-focus-listener.sh"

echo "=== ratbag-focus installer ==="
echo

# 1. Config
if [ ! -f "$SCRIPT_DIR/config.toml" ]; then
    cp "$SCRIPT_DIR/config.toml.example" "$SCRIPT_DIR/config.toml"
    echo "[!] Created config.toml from example."
    echo "    Edit $SCRIPT_DIR/config.toml before using ratbag-focus."
    echo "    Run 'ratbag-focus detect' to find your device's VID:PID and button indices."
    echo
fi

# 2. Make scripts executable
chmod +x "$SCRIPT_DIR/ratbag-focus"
chmod +x "$SCRIPT_DIR/src/apply.py"
chmod +x "$SCRIPT_DIR/src/switcher.py"
chmod +x "$SCRIPT_DIR/src/daemon.py"

# 3. Symlink CLI to ~/.local/bin
mkdir -p "$BIN_DIR"
ln -sf "$SCRIPT_DIR/ratbag-focus" "$BIN_DIR/ratbag-focus"
echo "[+] CLI linked: ratbag-focus -> $BIN_DIR/ratbag-focus"

# 4. Migrate old mouse-modifier service if present
if systemctl --user is-active mouse-modifier &>/dev/null; then
    echo "[~] Stopping old mouse-modifier service..."
    systemctl --user disable --now mouse-modifier.service 2>/dev/null || true
fi

# 5. Install systemd service
mkdir -p "$SYSTEMD_DIR"
cat > "$SYSTEMD_DIR/ratbag-focus-modifier.service" << EOF
[Unit]
Description=ratbag-focus modifier daemon
After=ratbagd.service

[Service]
ExecStart=/usr/bin/python3 $SCRIPT_DIR/src/daemon.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF
echo "[+] Systemd service installed: ratbag-focus-modifier.service"

# 6. FocusNotifier listener
if [ -d "$(dirname "$LISTENERS_FILE")" ]; then
    # Remove old listener if present
    OLD_LISTENER="$HOME/.config/mouse-profile-switcher.sh"
    if [ -f "$LISTENERS_FILE" ] && grep -qF "$OLD_LISTENER" "$LISTENERS_FILE"; then
        echo "[~] Removing old FocusNotifier listener..."
        grep -vF "$OLD_LISTENER" "$LISTENERS_FILE" > /tmp/.rfocus-listeners.tmp || true
        mv /tmp/.rfocus-listeners.tmp "$LISTENERS_FILE"
    fi

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
systemctl --user enable --now ratbag-focus-modifier.service
echo "[+] Modifier daemon enabled and running"

echo
echo "=== Done ==="
echo "  Edit $SCRIPT_DIR/config.toml to add profiles and app mappings."
echo "  Run 'ratbag-focus --help' for available commands."
