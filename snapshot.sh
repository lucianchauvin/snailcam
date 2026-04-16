#!/bin/bash
set -euo pipefail

SNAPSHOT_DIR="/home/snail/snapshots"
CLIMATE_LOG="$SNAPSHOT_DIR/climate.jsonl"
mkdir -p "$SNAPSHOT_DIR"

log_climate() {
    local ts
    ts=$(date +"%Y%m%d_%H%M%S")
    local resp
    resp=$(curl -s --max-time 4 http://192.168.88.241 2>/dev/null || echo "")
    if [[ -n "$resp" ]]; then
        local temp hum
        temp=$(echo "$resp" | sed -n 's/.*"temperature"[[:space:]]*:[[:space:]]*\([0-9.-]*\).*/\1/p' | head -1)
        hum=$(echo  "$resp" | sed -n 's/.*"humidity"[[:space:]]*:[[:space:]]*\([0-9.-]*\).*/\1/p'    | head -1)
        if [[ -n "$temp" ]]; then
            if [[ -n "$hum" ]]; then
                printf '{"t":"%s","temp":%s,"hum":%s}\n' "$ts" "$temp" "$hum" >> "$CLIMATE_LOG"
            else
                printf '{"t":"%s","temp":%s}\n'           "$ts" "$temp"        >> "$CLIMATE_LOG"
            fi
            echo "[$ts] Climate logged (temp=$temp${hum:+ hum=$hum})"
        fi
    fi
}

while true; do
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    TMP_FILE="/tmp/tmpsnailimg_$TIMESTAMP.jpg"
    OUT_FILE="$SNAPSHOT_DIR/$TIMESTAMP.jpg"

    # Fetch climate data from the sensor on every iteration, regardless of
    # whether the snapshot is saved (too dark, failed, etc.).
    log_climate

    if ffmpeg -y -loglevel error -i http://127.0.0.1:5000/api/video_feed -frames:v 1 "$TMP_FILE"; then
        if [[ ! -s "$TMP_FILE" ]]; then
            echo "[$TIMESTAMP] Empty snapshot — skipping."
            rm -f "$TMP_FILE"
            sleep 30
            log_climate
            sleep 30
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

    # Climate logs every 30 s; camera snapshots every 60 s.
    sleep 30
    log_climate
    sleep 30
done
