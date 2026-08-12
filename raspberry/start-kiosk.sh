#!/usr/bin/env bash
set -Eeuo pipefail

[[ -f /etc/cocktailbot/kiosk.env ]] && source /etc/cocktailbot/kiosk.env
URL="${COCKTAILBOT_KIOSK_URL:-http://127.0.0.1:8080}"
DELAY="${COCKTAILBOT_KIOSK_DELAY_SECONDS:-30}"
PROFILE="${COCKTAILBOT_CHROMIUM_PROFILE:-$HOME/.config/cocktailbot-chromium}"
LOCK="${XDG_RUNTIME_DIR:-/tmp}/cocktailbot-kiosk-${UID}.lock"

exec 9>"$LOCK"
flock -n 9 || exit 0

sleep "$DELAY"

for _ in $(seq 1 60); do
  curl -fsS --max-time 2 "$URL/api/status" >/dev/null 2>&1 && break
  sleep 1
done

if command -v chromium >/dev/null 2>&1; then
  BROWSER=chromium
elif command -v chromium-browser >/dev/null 2>&1; then
  BROWSER=chromium-browser
else
  echo "Chromium wurde nicht gefunden" >&2
  exit 1
fi

if [[ -n "${DISPLAY:-}" ]] && command -v xset >/dev/null 2>&1; then
  xset s off || true
  xset -dpms || true
  xset s noblank || true
fi

mkdir -p "$PROFILE"
while true; do
  "$BROWSER" \
    --kiosk \
    --no-first-run \
    --no-default-browser-check \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-translate \
    --disable-pinch \
    --overscroll-history-navigation=0 \
    --autoplay-policy=no-user-gesture-required \
    --user-data-dir="$PROFILE" \
    "$URL" || true
  sleep 2
done
