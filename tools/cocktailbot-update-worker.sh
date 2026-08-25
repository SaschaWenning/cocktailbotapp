#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE="/opt/cocktailbot/source"
LOG="/var/log/cocktailbot-update.log"

[[ $EUID -eq 0 ]] || {
  echo "Update-Worker muss als root laufen." >&2
  exit 1
}

exec >>"$LOG" 2>&1

echo
echo "============================================================"
echo "CocktailBot Software-Update: $(date --iso-8601=seconds)"
echo "============================================================"

if [[ ! -d "$SOURCE/.git" ]]; then
  echo "FEHLER: Git-Repository fehlt: $SOURCE"
  exit 1
fi

if [[ ! -f "$SOURCE/tools/update.sh" ]]; then
  echo "FEHLER: Update-Skript fehlt: $SOURCE/tools/update.sh"
  exit 1
fi

echo "[1/4] Hole origin/main"
git -c safe.directory=/opt/cocktailbot/source \
  -C /opt/cocktailbot/source fetch origin main

echo "[2/4] Setze lokale Quellen exakt auf origin/main"
git -c safe.directory=/opt/cocktailbot/source \
  -C /opt/cocktailbot/source reset --hard origin/main

echo "[3/4] Führe CocktailBot-Update aus"
bash /opt/cocktailbot/source/tools/update.sh

echo "[4/4] Update erfolgreich. Neustart."
sync
sleep 2
systemctl reboot
