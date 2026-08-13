# CocktailBot – PayPal-/Fortschritts-Update 2026-08-13

## Zubereitungs-Fortschritt

- Ursache behoben: `makeRecipe()` wartete bisher intern bis zum Ende des Pumpenjobs. Die Detailseite begann dadurch erst nach der Zubereitung mit der Fortschrittsabfrage.
- `MachineStore.waitUntilMachineIdle()` unterstützt jetzt einen Live-Status-Callback und ein frei wählbares Polling-Intervall.
- Während einer Cocktailzubereitung wird `/api/status` jetzt etwa alle 180–200 ms ausgewertet.
- Fortschritt, aktive Pumpen und Prozentanzeige werden dadurch während des laufenden Pumpenjobs aktualisiert.
- Nach Ende des Jobs springt die Anzeige sauber auf 100 %.

## PayPal Checkout

- Zahlungsstatus wird automatisch alle 2 Sekunden geprüft.
- Parallele/überlappende Statusabfragen werden verhindert.
- Nach bestätigter Zahlung wird der QR-Code sofort ausgeblendet.
- Stattdessen erscheint ein grüner Erfolgsstatus mit `Cocktail zubereiten`.
- Erst beim Drücken auf `Cocktail zubereiten` wird die PayPal-Order als verwendet markiert.
- Danach schließt sich die PayPal-Ansicht und die normale Cocktail-Zubereitungsansicht startet.
- Dadurch ist die PayPal-Zahlungsansicht während der eigentlichen Zubereitung nicht mehr im Weg und der normale Live-Fortschrittsdialog wird verwendet.

## Unverändert

- Offline-Gewerbelizenz und Lizenzdatei-Import bleiben erhalten.
- Popup-Tastatur V3 bleibt erhalten.
- Horizontale Top-Navigation im 1024×600-Querformat bleibt erhalten.
- Nicht blockierende Pico-2-LED-Firmware bleibt enthalten.

## Update-Skript

- `tools/update.sh` baut Updates jetzt standardmäßig direkt aus dem aktuellen Flutter-Quellcode (`--build-mode source`).
- Die vorhandene Relaislogik (`COCKTAILBOT_ACTIVE_HIGH`) wird weiterhin aus `/etc/cocktailbot/cocktailbot.env` übernommen. Damit bleibt die auf diesem Gerät benötigte LOW-aktive Relaiskonfiguration bei Updates erhalten.
