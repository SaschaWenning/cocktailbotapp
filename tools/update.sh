#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen." >&2; exit 1; }
ACTIVE_HIGH=1
PICO_PORT=auto
DELAY=30
if [[ -f /etc/cocktailbot/cocktailbot.env ]]; then
  ACTIVE_HIGH="$(grep -E '^COCKTAILBOT_ACTIVE_HIGH=' /etc/cocktailbot/cocktailbot.env | tail -1 | cut -d= -f2- || echo 1)"
  PICO_PORT="$(grep -E '^COCKTAILBOT_PICO_PORT=' /etc/cocktailbot/cocktailbot.env | tail -1 | cut -d= -f2- || echo auto)"
fi
if [[ -f /etc/cocktailbot/kiosk.env ]]; then
  DELAY="$(grep -E '^COCKTAILBOT_KIOSK_DELAY_SECONDS=' /etc/cocktailbot/kiosk.env | tail -1 | cut -d= -f2- || echo 30)"
fi
exec /opt/cocktailbot/source/install.sh \
  --active-high "${ACTIVE_HIGH:-1}" \
  --pico-port "${PICO_PORT:-auto}" \
  --kiosk-delay "${DELAY:-30}" \
  --skip-lcd --skip-boot-opt
