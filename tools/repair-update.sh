#!/usr/bin/env bash
set -Eeuo pipefail

[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen." >&2; exit 1; }
SOURCE="/opt/cocktailbot/source"
[[ -d "$SOURCE/.git" ]] || { echo "Git-Installation fehlt: $SOURCE" >&2; exit 1; }
state="$(systemctl is-active cocktailbot-self-update.service 2>/dev/null || true)"
case "$state" in
  active|activating|reloading|deactivating)
    echo "Ein Update läuft noch. Reparatur wird nicht parallel gestartet." >&2
    exit 1 ;;
esac

exec > >(tee -a /var/log/cocktailbot-update.log) 2>&1
echo "CocktailBot Update-Reparatur: $(date --iso-8601=seconds)"
curl -fsS --max-time 5 -X POST http://127.0.0.1:8080/api/command \
  -H 'Content-Type: application/json' -d '{"action":"stop"}' \
  || { echo "Pumpenstopp nicht bestätigt. Reparatur abgebrochen."; exit 1; }

echo "Entferne ausschließlich erzeugte Flutter-Builddateien und den Paket-Downloadcache."
rm -rf -- /opt/cocktailbot/source/app/build /opt/cocktailbot/source/app/.dart_tool
apt-get clean

echo "Lade zuerst die korrigierten Installationsskripte."
git -c safe.directory=/opt/cocktailbot/source -C "$SOURCE" fetch origin main
git -c safe.directory=/opt/cocktailbot/source -C "$SOURCE" reset --hard origin/main
python3 "$SOURCE/raspberry/update_state.py" start "Reparatur: geprüfter Web-Release wird installiert"
on_exit() {
  rc=$?
  if [[ "$rc" != "0" ]]; then
    python3 "$SOURCE/raspberry/update_state.py" failed "Reparatur fehlgeschlagen (Exit-Code $rc). Protokoll beachten." || true
  fi
}
trap on_exit EXIT
export COCKTAILBOT_SELF_UPDATE=1
bash "$SOURCE/tools/update.sh"
python3 "$SOURCE/raspberry/update_state.py" rebooting "Reparatur erfolgreich. Neustart läuft."
sync
systemctl reboot
