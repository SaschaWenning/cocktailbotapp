#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE="/opt/cocktailbot/source"
LOG="/var/log/cocktailbot-update.log"

[[ $EUID -eq 0 ]] || {
  echo "Update-Worker muss als root laufen." >&2
  exit 1
}

exec >>"$LOG" 2>&1

on_error() {
  rc=$?
  echo
  echo "FEHLER: Software-Update abgebrochen (Exit-Code $rc)"
  echo "Zeit: $(date --iso-8601=seconds)"
  echo "Es erfolgt KEIN automatischer Neustart."
  exit "$rc"
}
trap on_error ERR

echo
echo "============================================================"
echo "CocktailBot Software-Update: $(date --iso-8601=seconds)"
echo "============================================================"

[[ -d "$SOURCE/.git" ]] || { echo "FEHLER: Git-Repository fehlt: $SOURCE"; exit 1; }
[[ -f "$SOURCE/tools/update.sh" ]] || { echo "FEHLER: Update-Skript fehlt: $SOURCE/tools/update.sh"; exit 1; }

# Zeitreserve, damit Backend/Flutter die Startbestätigung sicher erhalten,
# bevor Quellen ersetzt oder cocktailbot.service neu gestartet werden.
echo "[0/4] Update angenommen. 5 Sekunden Startreserve für die Oberfläche."
sleep 5

echo "[1/4] Hole origin/main"
git -c safe.directory=/opt/cocktailbot/source \
  -C /opt/cocktailbot/source fetch origin main

echo "[2/4] Setze lokale Quellen exakt auf origin/main"
git -c safe.directory=/opt/cocktailbot/source \
  -C /opt/cocktailbot/source reset --hard origin/main

echo "[3/4] Führe CocktailBot-Update aus"
bash /opt/cocktailbot/source/tools/update.sh

echo "[4/4] Update erfolgreich. Neustart wird vorbereitet."
sync
sleep 3
echo "Neustart: $(date --iso-8601=seconds)"
systemctl reboot
