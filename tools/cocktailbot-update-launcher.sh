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

state="$(systemctl is-active "$UNIT" 2>/dev/null || true)"
case "$state" in
  active|activating|reloading|deactivating)
    echo "Ein CocktailBot-Software-Update läuft bereits."
    exit 75
    ;;
esac

# Alte fehlgeschlagene/stale transient units dürfen keinen neuen Start blockieren.
systemctl reset-failed "$UNIT" >/dev/null 2>&1 || true
for _ in 1 2 3 4 5; do
  if ! systemctl status "$UNIT" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

# Nur die Annahme des Jobs abwarten, nicht das komplette Update.
systemd-run \
  --no-block \
  --quiet \
  --unit=cocktailbot-self-update \
  --collect \
  --property=Type=oneshot \
  --property=TimeoutStartSec=infinity \
  --description="CocktailBot Software Update" \
  "$WORKER"

echo "CocktailBot-Software-Update wurde an systemd übergeben."
exit 0
