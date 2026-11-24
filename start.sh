#!/bin/bash
set -u

# Run this script from any directory; the project root is the script's directory.
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$PROJECT_DIR/data"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$DATA_DIR/nebula.pid"
PORT_FILE="$DATA_DIR/nebula.port"
LOG_FILE="$LOG_DIR/nebula.log"
HOST="127.0.0.1"

mkdir -p "$DATA_DIR" "$LOG_DIR"

# Prefer the project's virtual environment, then fall back to a system Python.
if [ -n "${PYTHON_BIN:-}" ]; then
  PYTHON="$PYTHON_BIN"
elif [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
  PYTHON="$PROJECT_DIR/.venv/bin/python"
elif [ -x "$PROJECT_DIR/venv/bin/python" ]; then
  PYTHON="$PROJECT_DIR/venv/bin/python"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON="$(command -v python3.12)"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  echo "Error: Python 3 was not found. Create .venv or set PYTHON_BIN." >&2
  exit 1
fi

open_dashboard() {
  local url="$1"
  if [ "${OPEN_BROWSER:-1}" = "1" ] && [ "$(uname -s)" = "Darwin" ]; then
    open "$url" >/dev/null 2>&1 || true
  fi
}

# If the tracked server is already healthy, reuse it instead of starting another.
if [ -f "$PID_FILE" ] && [ -f "$PORT_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  OLD_PORT="$(cat "$PORT_FILE" 2>/dev/null || true)"
  case "$OLD_PID:$OLD_PORT" in
    *[!0-9:]*|:*) ;;
    *)
      if kill -0 "$OLD_PID" 2>/dev/null && \
        curl --silent --show-error --fail --max-time 1 "http://$HOST:$OLD_PORT/api/health" >/dev/null 2>&1; then
        URL="http://$HOST:$OLD_PORT/#/dashboard"
        echo "Nebula is already running (PID $OLD_PID)."
        echo "Dashboard: $URL"
        open_dashboard "$URL"
        exit 0
      fi
      ;;
  esac
fi

find_free_port() {
  "$PYTHON" -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()'
}

# Ask the OS for a free port, then have main.py bind exactly that port.
# If another process wins the small gap between selection and binding, retry.
ATTEMPT=1
MAX_ATTEMPTS=8

while [ "$ATTEMPT" -le "$MAX_ATTEMPTS" ]; do
  PORT="$(find_free_port 2>/dev/null)"
  if ! echo "$PORT" | grep -Eq '^[0-9]+$'; then
    echo "Error: could not select a free local port." >&2
    exit 1
  fi

  cd "$PROJECT_DIR" || exit 1
  nohup "$PYTHON" -m backend.main --host "$HOST" --port "$PORT" --no-scan \
    >> "$LOG_FILE" 2>&1 < /dev/null &
  PID=$!

  printf '%s\n' "$PID" > "$PID_FILE"
  printf '%s\n' "$PORT" > "$PORT_FILE"

  READY=0
  CHECK=0
  while [ "$CHECK" -lt 50 ]; do
    if curl --silent --show-error --fail --max-time 1 \
      "http://$HOST:$PORT/api/health" >/dev/null 2>&1; then
      READY=1
      break
    fi

    if ! kill -0 "$PID" 2>/dev/null; then
      break
    fi

    sleep 0.5
    CHECK=$((CHECK + 1))
  done

  if [ "$READY" -eq 1 ]; then
    URL="http://$HOST:$PORT/#/dashboard"
    PAGE_CODE="$(curl --silent --output /dev/null --write-out '%{http_code}' \
      --max-time 3 "http://$HOST:$PORT/" 2>/dev/null || true)"

    echo "Nebula started in the background (PID $PID)."
    echo "Dashboard: $URL"
    echo "Log file: $LOG_FILE"

    case "$PAGE_CODE" in
      200) ;;
      *)
        echo "Warning: the API responds, but the frontend root returned HTTP ${PAGE_CODE:-unknown}."
        echo "Check that frontend/index.html exists and main.py serves the frontend directory."
        ;;
    esac

    open_dashboard "$URL"
    exit 0
  fi

  echo "Attempt $ATTEMPT/$MAX_ATTEMPTS did not become healthy on port $PORT."
  if kill -0 "$PID" 2>/dev/null; then
    kill -TERM "$PID" 2>/dev/null || true
    sleep 1
    kill -KILL "$PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE" "$PORT_FILE"
  ATTEMPT=$((ATTEMPT + 1))
done

echo "Error: Nebula did not start after $MAX_ATTEMPTS attempts." >&2
echo "Recent server log:" >&2
tail -n 40 "$LOG_FILE" >&2 2>/dev/null || true
exit 1