# Änderung: PayPal vollständig lokal auf dem Raspberry Pi

## Entfernt

- Cloudflare-Backend-URL aus der Flutter-Konfiguration
- Backend-Zugriffstoken aus Flutter/SharedPreferences
- externe `/create-order`, `/order-status`, `/mark-used`-Backend-URL
- externer QR-Code-Bilddienst

## Neu

- `/api/payment/status`
- `/api/payment/test`
- `/api/payment/config`
- `/api/payment/create-order`
- `/api/payment/order-status`
- `/api/payment/mark-used`
- PayPal Orders v2 direkt im Python-Dienst
- OAuth-Token nur serverseitig
- Sandbox/Live-Umschaltung
- SQLite-Datenbank `/var/lib/cocktailbot/payments.db`
- atomarer Einmalverbrauch bezahlter Orders
- serverseitige Preisermittlung
- serverseitige Betrags-/Währungsprüfung nach PayPal-Antwort
- lokales QR-Rendering mit `qr_flutter`
- `sudo cocktailbot-paypal-config`
- PayPal-Konfiguration standardmäßig direkt in `install.sh`
- PayPal-Backend und Abhängigkeiten werden immer installiert; Zugangsdaten werden erst später optional mit `sudo cocktailbot-paypal-config` eingetragen

## Secret-Speicher

```text
/etc/cocktailbot/paypal.env
```

Die Datei wird mit `0600 root:root` angelegt und bei normalen Updates nicht überschrieben.

## Installation ohne PayPal-Zwang

Das lokale PayPal-Backend und alle benötigten Python-Abhängigkeiten werden jetzt immer durch `install.sh` mitinstalliert. Der Installer fragt jedoch keine Client-ID und kein Client-Secret mehr ab. Maschinen ohne PayPal-Nutzung können daher normal installiert und betrieben werden. Bei Bedarf wird PayPal später mit `sudo cocktailbot-paypal-config` aktiviert.
