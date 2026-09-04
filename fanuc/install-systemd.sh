#!/bin/bash
set -euo pipefail

# Install fanuc-adapter as a systemd service on Debian.
# Run from anywhere; resolves the fanuc/ directory from this script's location.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FANUC_DIR="$SCRIPT_DIR"
SERVICE_NAME="fanuc-adapter"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ ! -x "${FANUC_DIR}/adapter" ]]; then
  echo "Error: ${FANUC_DIR}/adapter not found or not executable." >&2
  echo "Compile first: cd ${FANUC_DIR} && make" >&2
  exit 1
fi

if [[ ! -f "${FANUC_DIR}/adapter.ini" ]]; then
  echo "Error: ${FANUC_DIR}/adapter.ini not found." >&2
  exit 1
fi

touch "${FANUC_DIR}/fwlibeth.log"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Installing ${SERVICE_NAME} (requires sudo)..."
  exec sudo "$0" "$@"
fi

sed "s|@FANUC_DIR@|${FANUC_DIR}|g" \
  "${FANUC_DIR}/fanuc-adapter.service" > "${SERVICE_FILE}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "Installed: ${SERVICE_FILE}"
echo "Status:    systemctl status ${SERVICE_NAME}"
echo "Logs:      journalctl -u ${SERVICE_NAME} -f"
