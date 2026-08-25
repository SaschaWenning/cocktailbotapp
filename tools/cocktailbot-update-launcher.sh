#!/usr/bin/env bash
set -Eeuo pipefail

UNIT="cocktailbot-self-update.service"
WORKER="/usr/local/sbin/cocktailbot-update-worker"

[[ $EUID -eq 0 ]] || {
  echo "Update-Launcher muss als root laufen." >&2
  exit 1
}

[[ -x "$WORKER" ]] || {
  echo "Update-Worker fehlt: $WORKER" >&2
  exit 1
}

if systemctl is-active --quiet "$UNIT"; then
  echo "Ein CocktailBot-Software-Update läuft bereits."
  exit 75
fi

# Worker in eine eigene systemd-Unit auslagern. Dadurch überlebt das Update
# einen Neustart von cocktailbot.service innerhalb tools/update.sh.
exec systemd-run \
  --no-block \
  --unit=cocktailbot-self-update \
  --collect \
  --property=Type=oneshot \
  --property=TimeoutStartSec=infinity \
  --description="CocktailBot Software Update" \
  "$WORKER"
