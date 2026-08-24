#!/usr/bin/env bash
set -Eeuo pipefail

# LOW-aktive CocktailBot-Relais:
# HIGH = AUS, LOW = EIN
PINS=(17 18 27 22 23 24 25 4 5 6 13 19 26 16 20 21 12 15)

if command -v pinctrl >/dev/null 2>&1; then
  for pin in "${PINS[@]}"; do
    pinctrl set "$pin" op dh
  done

  failed=()
  for pin in "${PINS[@]}"; do
    state="$(pinctrl get "$pin" 2>&1 || true)"
    if ! grep -Eq '(^|[[:space:]])op([[:space:]].*)?dh([[:space:]]|$)' <<<"$state"; then
      failed+=("$pin:$state")
    fi
  done

  if ((${#failed[@]})); then
    echo "CocktailBot Pump Safety: nicht alle GPIOs sind HIGH/AUS:" >&2
    printf '  %s\n' "${failed[@]}" >&2
    exit 1
  fi
  exit 0
fi

if command -v raspi-gpio >/dev/null 2>&1; then
  for pin in "${PINS[@]}"; do
    raspi-gpio set "$pin" op dh
  done
  exit 0
fi

echo "CocktailBot Pump Safety: weder pinctrl noch raspi-gpio vorhanden." >&2
exit 1
