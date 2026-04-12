#!/bin/bash
set -euo pipefail

SNAPSHOT_DIR="/home/snail/snapshots"
mkdir -p "$SNAPSHOT_DIR"

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -d "$APP_DIR/build" ]]; then
    echo "Building SvelteKit app..."
    cd "$APP_DIR"
    npm run build
fi

PORT=5000 node "$APP_DIR/build/index.js" &
SERVER_PID=$!

cleanup() {
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

echo "Waiting for server to start..."
until curl -sf http://127.0.0.1:5000 >/dev/null; do
    sleep 1
done
echo "Server is up at http://0.0.0.0:5000"

"$APP_DIR/snapshot.sh" &
SNAP_PID=$!

wait "$SERVER_PID"
