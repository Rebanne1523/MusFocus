#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SYSTEMD_DIR="$HOME/.config/systemd/user"
LISTENER_SHIM="$HOME/.config/ratbag-focus-listener.sh"
LISTENERS_FILE="$HOME/.config/FocusNotifier/listeners.txt"

echo "=== ratbag-focus uninstaller ==="

systemctl --user disable --now ratbag-focus-modifier.service 2>/dev/null || true
rm -f "$SYSTEMD_DIR/ratbag-focus-modifier.service"
systemctl --user daemon-reload
echo "[+] Service removed"

rm -f "$BIN_DIR/ratbag-focus"
echo "[+] CLI symlink removed"

if [ -f "$LISTENERS_FILE" ]; then
    grep -vF "$LISTENER_SHIM" "$LISTENERS_FILE" > /tmp/.rfocus-listeners.tmp
    mv /tmp/.rfocus-listeners.tmp "$LISTENERS_FILE"
    echo "[+] FocusNotifier listener removed"
fi
rm -f "$LISTENER_SHIM"

rm -f /tmp/ratbag-focus-cache /tmp/ratbag-focus.lock

echo
echo "Config preserved at: $SCRIPT_DIR/config.toml"
echo "Project files preserved at: $SCRIPT_DIR"
echo "Delete the directory manually if you want a full removal."
