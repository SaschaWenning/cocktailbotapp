#!/usr/bin/env bash
set -Eeuo pipefail

[[ -f /etc/cocktailbot/kiosk.env ]] && source /etc/cocktailbot/kiosk.env
URL="${COCKTAILBOT_KIOSK_URL:-http://127.0.0.1:8080}"
DELAY="${COCKTAILBOT_KIOSK_DELAY_SECONDS:-30}"
PROFILE="${COCKTAILBOT_CHROMIUM_PROFILE:-$HOME/.config/cocktailbot-chromium}"
STOP_FILE="${COCKTAILBOT_KIOSK_STOP_FILE:-/var/lib/cocktailbot/kiosk.stop}"
LOCK="${XDG_RUNTIME_DIR:-/tmp}/cocktailbot-kiosk-${UID}.lock"

exec 9>"$LOCK"
flock -n 9 || exit 0

# Ein neuer manueller Start oder Desktop-Autostart hebt einen vorherigen
# absichtlichen "App schließen"-Zustand auf.
rm -f "$STOP_FILE" 2>/dev/null || true

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

# Flutter-Web/Service-Worker und Chromium-Cache dürfen nach einem Update keine
# alte 500-Seite oder einen alten Web-Build festhalten. Local Storage bleibt
# erhalten, damit CocktailBot-Einstellungen nicht verloren gehen.
clear_web_cache() {
  rm -rf \
    "$PROFILE/Default/Cache" \
    "$PROFILE/Default/Code Cache" \
    "$PROFILE/Default/GPUCache" \
    "$PROFILE/Default/Service Worker" \
    "$PROFILE/ShaderCache" \
    "$PROFILE/GrShaderCache" \
    2>/dev/null || true
}

clear_web_cache

while [[ ! -f "$STOP_FILE" ]]; do
  CACHE_BUSTER="$(date +%s%N)"
  "$BROWSER" \
    --kiosk \
    --no-first-run \
    --no-default-browser-check \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-translate \
    --disable-pinch \
    --disable-cache \
    --disk-cache-size=1 \
    --overscroll-history-navigation=0 \
    --touch-events=enabled \
    --autoplay-policy=no-user-gesture-required \
    --user-data-dir="$PROFILE" \
    "$URL/?v=$CACHE_BUSTER" || true

  [[ -f "$STOP_FILE" ]] && break
  clear_web_cache
  sleep 2
done
