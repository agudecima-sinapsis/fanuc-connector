#!/bin/bash
set -euo pipefail

# Install siemens-adapter as a systemd unit (outside Greengrass).
# The Python process is the SHDR producer on :7878. Ingest (Okuma-style)
# connects as a socket client and maps pipe keys. cppagent is not required.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADAPTER_DIR="$SCRIPT_DIR"
SYSTEMD_DIR="${ADAPTER_DIR}/systemd"
ENV_FILE="${ADAPTER_DIR}/adapter.env"
VENV_DIR="${ADAPTER_DIR}/venv"

if [[ ! -f "${ADAPTER_DIR}/adapter.py" ]]; then
  echo "Error: ${ADAPTER_DIR}/adapter.py not found." >&2
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Installing siemens-adapter (requires sudo)..."
  exec sudo "$0" "$@"
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${ADAPTER_DIR}/adapter.env.example" "${ENV_FILE}"
  echo "Wrote ${ENV_FILE} from adapter.env.example — set IP_MACHINE before starting."
fi

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install -r "${ADAPTER_DIR}/requirements.txt"

UNIT_SRC="${SYSTEMD_DIR}/siemens-adapter.service"
UNIT_DEST="/etc/systemd/system/siemens-adapter.service"
sed "s|@ADAPTER_DIR@|${ADAPTER_DIR}|g" "${UNIT_SRC}" > "${UNIT_DEST}"

systemctl daemon-reload
systemctl enable siemens-adapter
systemctl restart siemens-adapter

echo "Installed: ${UNIT_DEST}"
echo "SHDR:      TCP :7878 (pipe lines: mode, execution, alarm, optional program)"
echo "Status:    systemctl status siemens-adapter"
echo "Logs:      journalctl -u siemens-adapter -f"
echo "Rollback:  systemctl disable --now siemens-adapter"
