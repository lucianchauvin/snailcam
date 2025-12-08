#!/bin/bash
set -euo pipefail

source /home/snail/snailsite/.venv/bin/activate

SNAPSHOT_DIR="/home/snail/snapshots"
mkdir -p "$SNAPSHOT_DIR"

# Start Flask app in background
flask --app /home/snail/snailsite/app.py run --host=0.0.0.0 &
FLASK_PID=$!

cleanup() {
    echo "Stopping Flask server (PID $FLASK_PID)..."
    kill $FLASK_PID 2>/dev/null || true
    wait $FLASK_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

# Wait until Flask responds
echo "Waiting for Flask to start..."
until curl -s --head http://127.0.0.1:5000 | grep "200 OK" >/dev/null; do
    sleep 1
done
echo "Flask is up!"

while true; do
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    TMP_FILE="/tmp/tmpsnailimg_$TIMESTAMP.jpg"
    OUT_FILE="$SNAPSHOT_DIR/$TIMESTAMP.jpg"

    # Fetch ONE frame from the MJPEG stream
    # Use ffmpeg to grab one frame quickly and exit
    if ffmpeg -y -loglevel error -i http://127.0.0.1:5000/video_feed -frames:v 1 "$TMP_FILE"; then
        # Verify file exists and is readable
        if [[ ! -s "$TMP_FILE" ]]; then
            echo "[$TIMESTAMP] Empty snapshot — skipping."
            rm -f "$TMP_FILE"
            sleep 30
            continue
        fi

        BRIGHTNESS=$(magick "$TMP_FILE" -colorspace Gray -format "%[fx:mean]" info: 2>/dev/null || echo "0")
        if (( $(echo "$BRIGHTNESS > 0.1" | bc -l) )); then
            mv "$TMP_FILE" "$OUT_FILE"
            echo "[$TIMESTAMP] Saved bright snapshot (brightness=$BRIGHTNESS)"
        else
            echo "[$TIMESTAMP] Skipped dark snapshot (brightness=$BRIGHTNESS)"
            rm -f "$TMP_FILE"
        fi
    else
        echo "[$TIMESTAMP] Failed to fetch snapshot from /video_feed"
    fi

    sleep 60
done

