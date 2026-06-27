#!/usr/bin/env bash
set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────────────
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT="$DIR/setu_demo.mp4"
CHROME_PROFILE=/tmp/setu_chrome_profile
CHROME_LOG=/tmp/setu_chrome.log
FFMPEG_LOG=/tmp/setu_ffmpeg.log

CHROME_PID=""
FFMPEG_PID=""

# ── Cleanup trap ───────────────────────────────────────────────────────────
cleanup() {
  echo "[cleanup] Stopping ffmpeg and Chrome…"
  if [[ -n "$FFMPEG_PID" ]]; then
    kill -INT "$FFMPEG_PID" 2>/dev/null || true
    wait "$FFMPEG_PID" 2>/dev/null || true
  fi
  if [[ -n "$CHROME_PID" ]]; then
    kill "$CHROME_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# ── Kill any leftover CDP Chrome ───────────────────────────────────────────
echo "[run-demo] Killing any leftover CDP Chrome on port 9333…"
pkill -f "remote-debugging-port=9333" || true
rm -rf "$CHROME_PROFILE"
sleep 1

# ── Launch Chrome ──────────────────────────────────────────────────────────
echo "[run-demo] Launching Chrome → http://localhost:5173/"
DISPLAY=:1 /usr/bin/google-chrome \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9333 \
  --user-data-dir="$CHROME_PROFILE" \
  --no-first-run \
  --no-default-browser-check \
  --kiosk \
  --start-fullscreen \
  --enable-unsafe-webgpu \
  --enable-features=Vulkan,WebGPU \
  "http://localhost:5173/" \
  > "$CHROME_LOG" 2>&1 &
CHROME_PID=$!
echo "[run-demo] Chrome PID: $CHROME_PID"

# ── Wait for CDP to become reachable ──────────────────────────────────────
echo "[run-demo] Waiting for CDP on 127.0.0.1:9333…"
WAITED=0
until curl -sf http://127.0.0.1:9333/json/version > /dev/null 2>&1; do
  WAITED=$((WAITED + 1))
  if [[ $WAITED -ge 15 ]]; then
    echo "[ERROR] CDP did not become reachable within 15s. Chrome log:" >&2
    tail -20 "$CHROME_LOG" >&2
    exit 1
  fi
  sleep 1
done
echo "[run-demo] CDP reachable (waited ${WAITED}s)."

# ── Start ffmpeg screen recording ─────────────────────────────────────────
echo "[run-demo] Starting ffmpeg recording → $OUTPUT"
/usr/bin/ffmpeg -y \
  -f x11grab \
  -draw_mouse 0 \
  -framerate 30 \
  -video_size 1920x1080 \
  -i :1.0 \
  -c:v libx264 \
  -preset veryfast \
  -pix_fmt yuv420p \
  "$OUTPUT" \
  > "$FFMPEG_LOG" 2>&1 &
FFMPEG_PID=$!
echo "[run-demo] ffmpeg PID: $FFMPEG_PID"
sleep 1  # let ffmpeg start capturing

# ── Run the CDP click driver ───────────────────────────────────────────────
echo "[run-demo] Running click driver (record.mjs)…"
node "$DIR/record.mjs"

# ── Gracefully stop ffmpeg ─────────────────────────────────────────────────
echo "[run-demo] Stopping ffmpeg (SIGINT to flush moov atom)…"
kill -INT "$FFMPEG_PID"
wait "$FFMPEG_PID" 2>/dev/null || true
FFMPEG_PID=""  # prevent double-kill in trap

# ── Close Chrome ──────────────────────────────────────────────────────────
echo "[run-demo] Closing Chrome…"
kill "$CHROME_PID" 2>/dev/null || true
CHROME_PID=""  # prevent double-kill in trap

# ── Report ────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "Demo recording complete."
echo "Output: $OUTPUT"
ls -lh "$OUTPUT"
echo "============================================================"
