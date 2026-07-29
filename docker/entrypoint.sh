#!/bin/sh
set -eu

# Default bind for containers: listen on all interfaces inside the network namespace.
# Operators should still publish only the intended host port.
export SMART_PARKING_API_HOST="${SMART_PARKING_API_HOST:-0.0.0.0}"
export SMART_PARKING_API_PORT="${SMART_PARKING_API_PORT:-8000}"
export SMART_PARKING_OUTPUT_DIR="${SMART_PARKING_OUTPUT_DIR:-/app/output}"

mkdir -p "${SMART_PARKING_OUTPUT_DIR}"

if [ "$#" -eq 0 ]; then
  exec smart-parking serve --host "${SMART_PARKING_API_HOST}" --port "${SMART_PARKING_API_PORT}"
fi

case "$1" in
  smart-parking)
    exec "$@"
    ;;
  serve|process|benchmark|edit-spaces|export-events|db)
    exec smart-parking "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
