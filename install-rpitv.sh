#!/usr/bin/env bash
set -euo pipefail

PI_HOST="${PI_HOST:-rpitv}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Deploy the rpitv application to a Raspberry Pi.

Options:
  -H, --host HOST   SSH host or alias of the Raspberry Pi
                    Default: ${PI_HOST}
  -h, --help        Show this help text and exit

Examples:
  $(basename "$0")
  $(basename "$0") --host rpitv-bedroom
  PI_HOST=rpitv-livingroom $(basename "$0")
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -H|--host)
      if [[ $# -lt 2 ]]; then
        echo "Error: $1 requires a host name" >&2
        usage >&2
        exit 1
      fi
      PI_HOST="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

REMOTE_APP_DIR="/home/pi/Documents/rpitv"
LOCAL_APP_DIR="${LOCAL_APP_DIR:-$(pwd)}"
APP_USER="pi"
PYTHON_BIN="/usr/bin/python3"
SERVICE_NAME="rpitv"
DESCRIPTION="Raspberry Pi TV App - Ambilight and LED control"

# if [[ "${EUID}" -ne 0 ]]; then
#   echo "Run this as root: sudo bash deploy.sh"
#   exit 1
# fi

echo "==> Checking SSH connection to ${PI_HOST}"
ssh "${PI_HOST}" "echo 'SSH OK'"

echo "==> Creating target folder on the Pi"
ssh "${PI_HOST}" "mkdir -p ${REMOTE_APP_DIR}"

echo "==> Copying app files to the Pi"
rsync -avz --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'test*' \
  --exclude 'install-rpitv.sh' \
  --exclude 'build' \
  "${LOCAL_APP_DIR}/" "${PI_HOST}:${REMOTE_APP_DIR}/"

echo "==> Updating system packages"
ssh "${PI_HOST}" "
  cd '${REMOTE_APP_DIR}' &&
  ${PYTHON_BIN} -m pip install --upgrade pip setuptools wheel &&
  ${PYTHON_BIN} -m pip install --upgrade .
"

echo "==> Creating systemd service ${SERVICE_NAME} on the Pi"
ssh "${PI_HOST}" "sudo bash -s -- \"${SERVICE_NAME}\" \"${DESCRIPTION}\" \"${APP_USER}\" \"${PYTHON_BIN}\" \"${REMOTE_APP_DIR}\"" <<'REMOTE'
SERVICE_NAME="$1"
DESCRIPTION="$2"
APP_USER="$3"
PYTHON_BIN="$4"
APP_DIR="$5"

echo "==> Removing existing systemd service ${SERVICE_NAME} if present"
if systemctl cat "${SERVICE_NAME}.service" >/dev/null 2>&1; then
  systemctl stop "${SERVICE_NAME}.service" || true
  systemctl disable "${SERVICE_NAME}.service" || true
fi

rm -f \
  "/etc/systemd/system/${SERVICE_NAME}.service" \
  "/lib/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload

echo "...writing /lib/systemd/system/${SERVICE_NAME}.service"
cat > "/lib/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=${DESCRIPTION}
After=network.target

[Service]
WorkingDirectory=${APP_DIR}
#ExecStart=${PYTHON_BIN} ${APP_DIR}/src/rpitv/start_app.py
ExecStart=${PYTHON_BIN} -m rpitv.start_app
Restart=always
User=${APP_USER}

[Install]
WantedBy=multi-user.target
EOF

echo "==> Reloading systemd and enabling startup of ${SERVICE_NAME}"
sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo "==> Checking service status"
sudo systemctl status "${SERVICE_NAME}" --no-pager
REMOTE

echo "==> Deployment complete"