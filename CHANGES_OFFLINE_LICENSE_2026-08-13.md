# CocktailBot – Gerätegebundene Offline-Gewerbelizenz

## Ziel
Die Gewerbelizenz benötigt keinen Cloud-/Lizenzserver. Der Kunde sendet die in CocktailBot angezeigte Geräte-ID an den Betreiber. Der Betreiber erzeugt mit dem separaten Windows-Lizenzgenerator einen signierten `CBL1-...` Code. Dieser Code kann ausschließlich auf genau dieser Raspberry-Pi-Hardware aktiviert werden.

## Geräte-ID
Der Raspberry-Dienst bevorzugt `/proc/device-tree/chosen/rpi-machine-id`. Falls das auf älterer Firmware nicht vorhanden ist, wird die Hardware-Seriennummer verwendet. Daraus wird per SHA-256 eine kurze CocktailBot-ID im Format `CB-XXXX-XXXX-XXXX-XXXX` erzeugt. Die ID ist in der App nicht editierbar.

## Signatur
- Ed25519
- privater Schlüssel: ausschließlich im separaten Lizenzgenerator-Paket
- öffentlicher Schlüssel: `raspberry/license_public_key.pem`
- Signatur-Nachricht: `COCKTAILBOT-LICENSE|1|COMMERCIAL|<GERÄTE-ID>`
- Lizenzcode: `CBL1-` + URL-safe Base64 der 64-Byte-Signatur

Die App bzw. der Raspberry kennt nur den öffentlichen Schlüssel und kann daher Codes prüfen, aber keine neuen Lizenzen erzeugen.

## Raspberry API
- `GET /api/license/status`
- `POST /api/license/activate` mit `{ "code": "CBL1-..." }`
- `POST /api/license/deactivate`

Die aktive Lizenz wird unter `/var/lib/cocktailbot/license.json` mit Modus `0600` gespeichert. Bei jeder Statusprüfung wird Signatur und Gerätebindung erneut validiert. Kopieren der Lizenzdatei auf einen anderen Raspberry schaltet die Gewerbefunktionen dort nicht frei.

## Flutter-App
Die frühere editierbare Maschinen-ID und die Demo-/berechenbaren Codes wurden aus der Gewerbelizenz-Seite entfernt. Die App holt den autoritativen Lizenzstatus vom lokalen Raspberry-Dienst. Die Lizenzseite zeigt die echte Geräte-ID, bietet `Kopieren`, einen Lizenzcode-Eingang mit `Einfügen` sowie Aktivieren/Deaktivieren.

## PayPal
Der Zahlungs-Kassenmodus verwendet nach der Lizenzprüfung automatisch dieselbe Hardware-Geräte-ID. Die Maschinen-ID ist in den Zahlungseinstellungen nicht mehr frei editierbar. Kritische Zahlungs-API-Aktionen werden serverseitig zusätzlich durch eine aktive Gewerbelizenz geschützt.

## Installation
Der Installer installiert `python3-cryptography`, kopiert den öffentlichen Schlüssel nach `/etc/cocktailbot/license_public_key.pem` und setzt:

```text
COCKTAILBOT_LICENSE_FILE=/var/lib/cocktailbot/license.json
COCKTAILBOT_LICENSE_PUBLIC_KEY=/etc/cocktailbot/license_public_key.pem
```

## Wichtig
`cocktailbot_license_private_key.pem` aus dem Lizenzgenerator-Paket darf niemals in GitHub oder auf Kunden-Raspberrys gelangen. Ohne diesen privaten Schlüssel können keine neuen zu diesem App-Build passenden Gewerbelizenzen ausgestellt werden.
