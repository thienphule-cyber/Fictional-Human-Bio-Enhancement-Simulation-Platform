#!/bin/bash
set -u

# Run this script from any directory; the project root is the script's directory.
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_DIR/data/nebula.pid"
PORT_FILE="$PROJECT_DIR/data/nebula.port"

if [ ! -f "$PID_FILE" ]; then
  echo "No Nebula PID file found; no process was signalled."
  exit 0
fi

PID="$(cat "$PID_FILE" 2>/dev/null || true)"
PORT="$(cat "$PORT_FILE" 2>/dev/null || true)"

case "$PID" in
  ''|*[!0-9]*)
    echo "Invalid PID in $PID_FILE; removing the stale PID record."
    rm -f "$PID_FILE" "$PORT_FILE"
    exit 1
    ;;
esac

is_nebula_process() {
  local command_line
  command_line="$(ps -p "$PID" -o command= 2>/dev/null || true)"
  case "$command_line" in
    *backend.main*) return 0 ;;
    *) return 1 ;;
  esac
}

if ! kill -0 "$PID" 2>/dev/null; then
  echo "Nebula process $PID is not running; clearing stale PID/port records."
  rm -f "$PID_FILE" "$PORT_FILE"
  exit 0
fi

# Never signal a process unless its command line identifies the Nebula module.
if ! is_nebula_process; then
  echo "PID $PID is not identifiable as backend.main; no process was signalled." >&2
  echo "Removing stale PID/port records only." >&2
  rm -f "$PID_FILE" "$PORT_FILE"
  exit 1
fi

echo "Stopping Nebula (PID $PID${PORT:+, port $PORT})…"
kill -TERM "$PID" 2>/dev/null || true

WAITED=0
while [ "$WAITED" -lt 15 ]; do
  if ! kill -0 "$PID" 2>/dev/null || ! is_nebula_process; then
    break
  fi
  sleep 1
  WAITED=$((WAITED + 1))
done

if kill -0 "$PID" 2>/dev/null && is_nebula_process; then
  echo "Nebula did not stop after 15 seconds; sending SIGKILL." >&2
  kill -KILL "$PID" 2>/dev/null || true
  sleep 1
fi

if kill -0 "$PID" 2>/dev/null && is_nebula_process; then
  echo "Error: Nebula process $PID is still running." >&2
  exit 1
fi

rm -f "$PID_FILE" "$PORT_FILE"
echo "Nebula stopped."