#!/bin/bash
set -euo pipefail

# Install siemens-adapter + siemens-mtcagent as systemd units (outside Greengrass).
# Run from anywhere; resolves this tree from the script location (Fanuc analog).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADAPTER_DIR="$SCRIPT_DIR"
SYSTEMD_DIR="${ADAPTER_DIR}/systemd"
ENV_FILE="${ADAPTER_DIR}/adapter.env"
VENV_DIR="${ADAPTER_DIR}/venv"
AGENT_BIN="${AGENT_BIN:-/usr/local/bin/agent}"
PRE_SCRIPT="${ADAPTER_DIR}/install-cppagent.sh"

if [[ ! -f "${ADAPTER_DIR}/adapter.py" ]]; then
  echo "Error: ${ADAPTER_DIR}/adapter.py not found." >&2
  exit 1
fi

if [[ ! -f "${ADAPTER_DIR}/agent/agent.cfg" || ! -f "${ADAPTER_DIR}/agent/Devices.xml" ]]; then
  echo "Error: agent/agent.cfg or agent/Devices.xml missing." >&2
  exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Installing siemens adapter units (requires sudo)..."
  exec sudo --preserve-env=AGENT_BIN,CPPAGENT_SRC,CPPAGENT_JOBS,CPPAGENT_REPO "$0" "$@"
fi

if [[ ! -x "${PRE_SCRIPT}" ]]; then
  echo "Error: ${PRE_SCRIPT} not found or not executable." >&2
  exit 1
fi
"${PRE_SCRIPT}"

if [[ ! -x "${AGENT_BIN}" ]]; then
  echo "Error: cppagent still missing at ${AGENT_BIN} after ${PRE_SCRIPT}." >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${ADAPTER_DIR}/adapter.env.example" "${ENV_FILE}"
  echo "Wrote ${ENV_FILE} from adapter.env.example — set IP_MACHINE before starting."
fi

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install -r "${ADAPTER_DIR}/requirements.txt"

install_unit() {
  local name="$1"
  local src="${SYSTEMD_DIR}/${name}.service"
  local dest="/etc/systemd/system/${name}.service"
  sed "s|@ADAPTER_DIR@|${ADAPTER_DIR}|g" "${src}" > "${dest}"
}

install_unit siemens-adapter
install_unit siemens-mtcagent

systemctl daemon-reload
systemctl enable siemens-adapter siemens-mtcagent
systemctl restart siemens-adapter siemens-mtcagent

echo "Installed: /etc/systemd/system/siemens-adapter.service"
echo "Installed: /etc/systemd/system/siemens-mtcagent.service"
echo "Status:    systemctl status siemens-adapter siemens-mtcagent"
echo "Logs:      journalctl -u siemens-adapter -u siemens-mtcagent -f"
echo "Rollback:  systemctl disable --now siemens-adapter siemens-mtcagent"
