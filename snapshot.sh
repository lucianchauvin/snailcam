#!/bin/bash
set -euo pipefail

SNAPSHOT_DIR="/home/snail/snapshots"
CLIMATE_LOG="$SNAPSHOT_DIR/climate.jsonl"
mkdir -p "$SNAPSHOT_DIR"

while true; do
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    TMP_FILE="/tmp/tmpsnailimg_$TIMESTAMP.jpg"
    OUT_FILE="$SNAPSHOT_DIR/$TIMESTAMP.jpg"

    # Fetch climate data from the sensor on every iteration, regardless of
    # whether the snapshot is saved (too dark, failed, etc.).
    CLIMATE_RESP=$(curl -s --max-time 4 http://192.168.88.241 2>/dev/null || echo "")
    if [[ -n "$CLIMATE_RESP" ]]; then
        TEMP=$(echo "$CLIMATE_RESP" | sed -n 's/.*"temperature"[[:space:]]*:[[:space:]]*\([0-9.-]*\).*/\1/p' | head -1)
        HUM=$(echo  "$CLIMATE_RESP" | sed -n 's/.*"humidity"[[:space:]]*:[[:space:]]*\([0-9.-]*\).*/\1/p'    | head -1)
        if [[ -n "$TEMP" ]]; then
            if [[ -n "$HUM" ]]; then
                printf '{"t":"%s","temp":%s,"hum":%s}\n' "$TIMESTAMP" "$TEMP" "$HUM" >> "$CLIMATE_LOG"
            else
                printf '{"t":"%s","temp":%s}\n'           "$TIMESTAMP" "$TEMP"        >> "$CLIMATE_LOG"
            fi
            echo "[$TIMESTAMP] Climate logged (temp=$TEMP${HUM:+ hum=$HUM})"
        fi
    fi

    if ffmpeg -y -loglevel error -i http://127.0.0.1:5000/api/video_feed -frames:v 1 "$TMP_FILE"; then
        if [[ ! -s "$TMP_FILE" ]]; then
            echo "[$TIMESTAMP] Empty snapshot — skipping."
            rm -f "$TMP_FILE"
            sleep 60
            continue
        fi

        BRIGHTNESS=$(magick "$TMP_FILE" -colorspace Gray -format "%[fx:mean]" info: 2>/dev/null || echo "0")
        if (( $(echo "$BRIGHTNESS > 0.26" | bc -l) )); then
            mv "$TMP_FILE" "$OUT_FILE"
            echo "[$TIMESTAMP] Saved snapshot (brightness=$BRIGHTNESS)"
        else
            echo "[$TIMESTAMP] Skipped dark snapshot (brightness=$BRIGHTNESS)"
            rm -f "$TMP_FILE"
        fi
    else
        echo "[$TIMESTAMP] Failed to fetch snapshot"
    fi

    sleep 60
done
