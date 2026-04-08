#!/bin/bash
set -euo pipefail

source /home/snail/snailsite/.venv/bin/activate

SNAPSHOT_DIR="/home/snail/snapshots"
mkdir -p "$SNAPSHOT_DIR"

while true; do
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    TMP_FILE="/tmp/tmpsnailimg_$TIMESTAMP.jpg"
    OUT_FILE="$SNAPSHOT_DIR/$TIMESTAMP.jpg"

    if ffmpeg -y -loglevel error -i http://127.0.0.1:5000/video_feed -frames:v 1 "$TMP_FILE"; then
        # Verify file exists and is readable
        if [[ ! -s "$TMP_FILE" ]]; then
            echo "[$TIMESTAMP] Empty snapshot — skipping."
            rm -f "$TMP_FILE"
            sleep 30
            continue
        fi

        BRIGHTNESS=$(magick "$TMP_FILE" -colorspace Gray -format "%[fx:mean]" info: 2>/dev/null || echo "0")
        if (( $(echo "$BRIGHTNESS > 0.26" | bc -l) )); then
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

