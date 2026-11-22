#!/usr/bin/env bash
set -euo pipefail

PI_HOST="${PI_HOST:-rpitv}"
SERVERNAME="rpitv"
PORT="${PORT:-5000}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Deploy the rpitv application to a Raspberry Pi.

Options:
  -H, --host HOST   SSH host or alias of the Raspberry Pi
                    Default: ${PI_HOST}
  -n, --servername NAME
                    mDNS hostname advertised by the app (default: ${SERVERNAME})
  -p, --port PORT   Port number for the app (default: ${PORT})
  -h, --help        Show this help text and exit

Examples:
  $(basename "$0")
  $(basename "$0") --host pi@192.168.0.35
  $(basename "$0") --servername rpitv
  $(basename "$0") --port 5000
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
    -n|--servername)
      if [[ $# -lt 2 ]]; then
        echo "Error: $1 requires a hostname" >&2
        usage >&2
        exit 1
      fi
      SERVERNAME="$2"
      shift 2
      ;;
    -p|--port)
      if [[ $# -lt 2 ]]; then
        echo "Error: $1 requires a port number" >&2
        usage >&2
        exit 1
      fi
      PORT="$2"
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

if [[ ! "$SERVERNAME" =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]]; then
  echo "Error: servername must be a valid hostname label" >&2
  exit 1
fi

if [[ ! "$PORT" =~ ^[0-9]{1,5}$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "Error: port must be a number between 1 and 65535" >&2
  exit 1
fi

REMOTE_APP_DIR="/home/pi/Documents/rpitv"
LOCAL_APP_DIR="${LOCAL_APP_DIR:-$(pwd)}"
APP_USER="pi"
PYTHON_BIN="${REMOTE_APP_DIR}/.venv/bin/python"
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

echo "==> Creating virtual environment and installing dependencies on the Pi"
ssh "${PI_HOST}" "
  cd '${REMOTE_APP_DIR}' &&
  if [ ! -x .venv/bin/python ]; then
    /usr/bin/python3 -m venv --system-site-packages .venv &&
    .venv/bin/pip install --upgrade pip setuptools wheel
  fi
  .venv/bin/pip install .
"

echo "==> Compiling Arduino sketch and uploading to the Arduino"
if ! ssh "${PI_HOST}" "
  ${PYTHON_BIN} '${REMOTE_APP_DIR}/src/rpitv/arduino_setup.py' &&
  cd '${REMOTE_APP_DIR}/src/rpitv' &&
  /home/pi/local/bin/arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328old arduino_pixel  &&
  /home/pi/local/bin/arduino-cli upload -p /dev/ttyUSB0 --fqbn arduino:avr:nano:cpu=atmega328old arduino_pixel  
"; then
  echo "Warning: Arduino upload failed" >&2
fi

echo "==> Creating systemd service ${SERVICE_NAME} on the Pi"
ssh "${PI_HOST}" "sudo bash -s -- \"${SERVICE_NAME}\" \"${DESCRIPTION}\" \"${APP_USER}\" \"${PYTHON_BIN}\" \"${REMOTE_APP_DIR}\" \"${SERVERNAME}\" \"${PORT}\" " <<'REMOTE'
SERVICE_NAME="$1"
DESCRIPTION="$2"
APP_USER="$3"
PYTHON_BIN="$4"
APP_DIR="$5"
SERVERNAME="$6"
PORT="$7"

PORT_CAPABILITY=""
if (( PORT < 1024 )); then
  PORT_CAPABILITY="AmbientCapabilities=CAP_NET_BIND_SERVICE"
fi

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
ExecStart=${PYTHON_BIN} -m rpitv.start_app --servername ${SERVERNAME} --port ${PORT}
${PORT_CAPABILITY}
ExecStop=/bin/kill -s SIGTERM $MAINPID
TimeoutStopSec=30
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