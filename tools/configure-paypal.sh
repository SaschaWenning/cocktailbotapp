#!/usr/bin/env bash
set -Eeuo pipefail

ENV_FILE=/etc/cocktailbot/paypal.env
NONINTERACTIVE="${COCKTAILBOT_PAYPAL_NONINTERACTIVE:-0}"
[[ "${1:-}" == "--non-interactive" ]] && NONINTERACTIVE=1
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen." >&2; exit 1; }

CURRENT_MODE=sandbox
CURRENT_ID=""
CURRENT_SECRET=""
CURRENT_RETURN=""
CURRENT_CANCEL=""
if [[ -f "$ENV_FILE" ]]; then
  CURRENT_MODE="$(grep -E '^COCKTAILBOT_PAYPAL_MODE=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
  CURRENT_ID="$(grep -E '^COCKTAILBOT_PAYPAL_CLIENT_ID=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
  CURRENT_SECRET="$(grep -E '^COCKTAILBOT_PAYPAL_CLIENT_SECRET=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
  CURRENT_RETURN="$(grep -E '^COCKTAILBOT_PAYPAL_RETURN_URL=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
  CURRENT_CANCEL="$(grep -E '^COCKTAILBOT_PAYPAL_CANCEL_URL=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
fi

if [[ "$NONINTERACTIVE" == "1" ]]; then
  MODE="${COCKTAILBOT_PAYPAL_MODE:-${CURRENT_MODE:-sandbox}}"
  CLIENT_ID="${COCKTAILBOT_PAYPAL_CLIENT_ID:-$CURRENT_ID}"
  CLIENT_SECRET="${COCKTAILBOT_PAYPAL_CLIENT_SECRET:-$CURRENT_SECRET}"
  RETURN_URL="${COCKTAILBOT_PAYPAL_RETURN_URL:-$CURRENT_RETURN}"
  CANCEL_URL="${COCKTAILBOT_PAYPAL_CANCEL_URL:-$CURRENT_CANCEL}"
else
  echo
  echo "============================================================"
  echo "PayPal-Konfiguration für CocktailBot"
  echo "Die Zugangsdaten werden nur lokal unter $ENV_FILE gespeichert."
  echo "Für den ersten Test wird 'sandbox' empfohlen."
  echo "============================================================"
  echo

  read -r -p "PayPal Modus [sandbox/live] (${CURRENT_MODE:-sandbox}): " MODE
  MODE="${MODE:-${CURRENT_MODE:-sandbox}}"

  read -r -p "PayPal Client-ID${CURRENT_ID:+ [vorhanden - Enter = behalten]}: " CLIENT_ID
  CLIENT_ID="${CLIENT_ID:-$CURRENT_ID}"

  if [[ -n "$CURRENT_SECRET" ]]; then
    read -r -s -p "PayPal Client-Secret [vorhanden - Enter = behalten]: " CLIENT_SECRET
    echo
    CLIENT_SECRET="${CLIENT_SECRET:-$CURRENT_SECRET}"
  else
    read -r -s -p "PayPal Client-Secret: " CLIENT_SECRET
    echo
  fi

  read -r -p "Return-URL (leer = PayPal-Startseite)${CURRENT_RETURN:+ [$CURRENT_RETURN]}: " RETURN_URL
  RETURN_URL="${RETURN_URL:-$CURRENT_RETURN}"
  read -r -p "Cancel-URL (leer = Return-URL)${CURRENT_CANCEL:+ [$CURRENT_CANCEL]}: " CANCEL_URL
  CANCEL_URL="${CANCEL_URL:-$CURRENT_CANCEL}"
fi

[[ "$MODE" == sandbox || "$MODE" == live ]] || { echo "Ungültiger Modus: $MODE" >&2; exit 2; }
[[ -n "$CLIENT_ID" ]] || { echo "Client-ID darf nicht leer sein." >&2; exit 2; }
[[ -n "$CLIENT_SECRET" ]] || { echo "Client-Secret darf nicht leer sein." >&2; exit 2; }

for value in "$CLIENT_ID" "$CLIENT_SECRET" "$RETURN_URL" "$CANCEL_URL"; do
  [[ "$value" != *$'\n'* && "$value" != *$'\r'* ]] || { echo "Zeilenumbrüche sind nicht erlaubt." >&2; exit 2; }
done

install -d -m 0755 /etc/cocktailbot
umask 077
cat > "$ENV_FILE" <<ENV
COCKTAILBOT_PAYPAL_MODE=$MODE
COCKTAILBOT_PAYPAL_CLIENT_ID=$CLIENT_ID
COCKTAILBOT_PAYPAL_CLIENT_SECRET=$CLIENT_SECRET
COCKTAILBOT_PAYMENT_DB=/var/lib/cocktailbot/payments.db
COCKTAILBOT_PAYPAL_BRAND_NAME=CocktailBot
COCKTAILBOT_PAYPAL_RETURN_URL=$RETURN_URL
COCKTAILBOT_PAYPAL_CANCEL_URL=$CANCEL_URL
COCKTAILBOT_PAYPAL_TIMEOUT_SECONDS=15
ENV
chown root:root "$ENV_FILE"
chmod 0600 "$ENV_FILE"

systemctl restart cocktailbot.service
sleep 2

echo
echo "Lokales Zahlungsbackend:"
curl -fsS http://127.0.0.1:8080/api/payment/status || true
echo
echo
echo "Teste PayPal OAuth-Zugang ..."
if curl -fsS -X POST http://127.0.0.1:8080/api/payment/test; then
  echo
  echo "PayPal-Verbindung erfolgreich."
else
  echo
  echo "PayPal-Test fehlgeschlagen. Prüfe: journalctl -u cocktailbot.service -n 100" >&2
  exit 1
fi
