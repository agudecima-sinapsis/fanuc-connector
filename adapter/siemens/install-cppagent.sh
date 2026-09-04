#!/bin/bash
set -euo pipefail

# Put the cppagent binary at AGENT_BIN (default /usr/local/bin/agent).
# Idempotent: exits 0 if that path is already executable.
# Does NOT enable cppagent's own systemd unit (it would steal port 5000).
#
# First run on a Pi compiles C++ and can take 30–90+ minutes. Needs ~3GB
# RAM+swap; override parallelism with CPPAGENT_JOBS (default 1).

AGENT_BIN="${AGENT_BIN:-/usr/local/bin/agent}"
SRC_DIR="${CPPAGENT_SRC:-/opt/cppagent}"
JOBS="${CPPAGENT_JOBS:-1}"
REPO="${CPPAGENT_REPO:-https://github.com/mtconnect/cppagent.git}"
VENV_DIR="${CPPAGENT_VENV:-/opt/cppagent-venv}"
PACK_DIR="${CPPAGENT_PACK:-/opt/cppagent-pack}"

if [[ -x "${AGENT_BIN}" ]]; then
  echo "cppagent already installed: ${AGENT_BIN}"
  exit 0
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Installing cppagent to ${AGENT_BIN} (requires sudo)..."
  exec sudo --preserve-env=AGENT_BIN,CPPAGENT_SRC,CPPAGENT_JOBS,CPPAGENT_REPO,CPPAGENT_VENV,CPPAGENT_PACK "$0" "$@"
fi

export DEBIAN_FRONTEND=noninteractive
echo "Installing build packages (this is slow the first time)..."
apt-get update
apt-get install -y \
  build-essential \
  cmake \
  git \
  python3 \
  python3-pip \
  python3-venv \
  autoconf \
  automake

if [[ ! -x "${VENV_DIR}/bin/conan" ]]; then
  python3 -m venv "${VENV_DIR}"
  "${VENV_DIR}/bin/pip" install --upgrade pip
  "${VENV_DIR}/bin/pip" install conan
fi

if [[ ! -d "${SRC_DIR}/.git" ]]; then
  echo "Cloning ${REPO} → ${SRC_DIR}"
  git clone --depth 1 "${REPO}" "${SRC_DIR}"
fi

PARENT="$(dirname "${SRC_DIR}")"
NAME="$(basename "${SRC_DIR}")"
mkdir -p "${PACK_DIR}"

echo "Building cppagent with Conan (jobs=${JOBS}). Do not use cppagent's mtcagent.service."
export PATH="${VENV_DIR}/bin:${PATH}"
cd "${PARENT}"
conan profile detect --force
conan create "${NAME}" \
  -pr "${NAME}/conan/profiles/gcc" \
  --build=missing \
  --test-folder= \
  -c "tools.build:jobs=${JOBS}" \
  -o with_ruby=False \
  -o cpack=True \
  -o "cpack_destination=${PACK_DIR}" \
  -o cpack_name=dist \
  -o cpack_generator=TGZ

tar -xf "${PACK_DIR}/dist.tar.gz" -C "${PACK_DIR}"

BIN=""
if [[ -x "${PACK_DIR}/dist/bin/agent" ]]; then
  BIN="${PACK_DIR}/dist/bin/agent"
elif [[ -x "${PACK_DIR}/dist/bin/mtcagent" ]]; then
  BIN="${PACK_DIR}/dist/bin/mtcagent"
elif [[ -x "${PACK_DIR}/bin/agent" ]]; then
  BIN="${PACK_DIR}/bin/agent"
elif [[ -x "${PACK_DIR}/bin/mtcagent" ]]; then
  BIN="${PACK_DIR}/bin/mtcagent"
else
  echo "Error: built cppagent but could not find dist/bin/agent or mtcagent under ${PACK_DIR}" >&2
  ls -la "${PACK_DIR}" "${PACK_DIR}/dist" "${PACK_DIR}/dist/bin" 2>/dev/null || true
  exit 1
fi

install -m 0755 "${BIN}" "${AGENT_BIN}"
echo "Installed ${BIN} → ${AGENT_BIN}"
"${AGENT_BIN}" --help >/dev/null 2>&1 || true
ls -l "${AGENT_BIN}"
