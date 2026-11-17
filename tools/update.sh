#!/usr/bin/env bash
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen." >&2; exit 1; }

ACTIVE_HIGH=0
PICO_PORT=auto
GPIO_CHIP=auto
DELAY=30
FORCE_X11_1024X600=0

if [[ -f /etc/cocktailbot/cocktailbot.env ]]; then
  ACTIVE_HIGH="$(grep -E '^COCKTAILBOT_ACTIVE_HIGH=' /etc/cocktailbot/cocktailbot.env | tail -1 | cut -d= -f2- || echo 0)"
  PICO_PORT="$(grep -E '^COCKTAILBOT_PICO_PORT=' /etc/cocktailbot/cocktailbot.env | tail -1 | cut -d= -f2- || echo auto)"
  GPIO_CHIP="$(grep -E '^COCKTAILBOT_GPIO_CHIP=' /etc/cocktailbot/cocktailbot.env | tail -1 | cut -d= -f2- || echo auto)"
fi

if [[ -f /etc/cocktailbot/kiosk.env ]]; then
  DELAY="$(grep -E '^COCKTAILBOT_KIOSK_DELAY_SECONDS=' /etc/cocktailbot/kiosk.env | tail -1 | cut -d= -f2- || echo 30)"
  FORCE_X11_1024X600="$(grep -E '^COCKTAILBOT_FORCE_X11_1024X600=' /etc/cocktailbot/kiosk.env | tail -1 | cut -d= -f2- || echo 0)"
fi

export COCKTAILBOT_FORCE_X11_1024X600="${FORCE_X11_1024X600:-0}"

# The Pi installs the already-built release only after its app/workflow hashes
# match main. Do not fill the SD card by compiling Flutter during an update.
# These two folders contain generated build files, never recipes or settings.
rm -rf -- /opt/cocktailbot/source/app/build /opt/cocktailbot/source/app/.dart_tool
apt-get clean
free_kb="$(df -Pk /opt/cocktailbot | awk 'NR==2 {print $4}')"
if [[ ! "$free_kb" =~ ^[0-9]+$ ]] || (( free_kb < 524288 )); then
  echo "Update abgebrochen: mindestens 512 MiB freier Speicher auf /opt/cocktailbot erforderlich." >&2
  df -h /opt/cocktailbot >&2
  exit 1
fi

exec bash /opt/cocktailbot/source/install.sh \
  --active-high "${ACTIVE_HIGH:-0}" \
  --pico-port "${PICO_PORT:-auto}" \
  --gpio-chip "${GPIO_CHIP:-auto}" \
  --kiosk-delay "${DELAY:-30}" \
  --skip-lcd --skip-boot-opt \
  --build-mode release \
  "$@"
