# CocktailBot 2.6 – Pumpensteuerung und Beleuchtung

Es gibt zwei unabhängige Auswahlen an den passenden Stellen:

- Oben unter **Einstellungen → Kalibrierung**: **Relais – bisheriger Aufbau** oder **MOSFET-Platine – Cocktailbot V2**.
- Unter **Einstellungen → LED-Beleuchtung**: **Pico 2 – bisherige 240 LEDs** oder **24-LED-Ring – über die Platine**.

Ohne gespeicherte Auswahl bleiben Relais und Pico der Standard.
Die Auswahl wird auf dem Raspberry Pi in `/var/lib/cocktailbot/hardware.json`
gespeichert und bleibt bei Neustarts und Softwareupdates erhalten. Browser- und
Rezeptdaten ändern die Hardwareauswahl nicht. Der bisherige Pico braucht keine
neue Firmware.

## Diese lokale Version installieren

Das Softwarepaket auf dem Raspberry Pi in einen eigenen Ordner entpacken,
beispielsweise `~/cocktailbot-hardware`. **Nicht direkt in
`/opt/cocktailbot/source` entpacken**, da der Installer diesen Zielordner ersetzt.
Die 12-V-Versorgung von Platine bzw. Relais zunächst trennen. Im entpackten Ordner:

```bash
sudo bash install.sh --local-source --skip-lcd --skip-boot-opt --build-mode source --reboot
```

Dieser Befehl übernimmt die entpackten Änderungen und baut die neue Oberfläche.
Er benötigt Internet und ein 64-Bit-Raspberry-Pi-OS. Er lädt den Quellcode bei
dieser Installation nicht erneut von GitHub.

Anschließend die gewünschte Hardware auf der jeweiligen Einstellungsseite auswählen
und **Pumpensteuerung übernehmen** bzw. **LED-Aufbau übernehmen** drücken.
Die Nachfrage erst bestätigen, nachdem alle Pumpen gestoppt
sind und die 12-V-Versorgung getrennt ist. Danach Versorgung anschließen und
zunächst einen Ausgang testen. Eine Umstellung bei laufenden Pumpen wird
abgewiesen. Hardware nur vollständig stromlos umstecken, einschließlich Pi.

## 24-LED-Ring an der V2-Platine

- WS2812B-Ring mit 24 LEDs, Daten über **BCM9 / physischen Pin 21**.
- Anschluss gemäß Platinenbeschriftung: **+5 V, GND, DATA**. Die 5-V-Versorgung
  kommt vom Step-down-Modul, der Raspberry Pi bleibt separat versorgt.
- Raspberry Pi 5, 64-Bit-Raspberry-Pi-OS und verfügbares `/dev/pio0` erforderlich.
- Der Installer installiert den RP1-PIO-Treiber und setzt dessen Zugriffsrechte.
  Er aktualisiert nicht automatisch Kernel oder EEPROM.
- Fehlt `/dev/pio0`, verweigert die App die Umstellung mit einer Fehlermeldung.
  In diesem Fall Raspberry Pi OS über seine regulären Updates aktualisieren und
  neu starten. Die vorherige Hardwareauswahl bleibt erhalten.
- Der Treiber nutzt PIO, **nicht SPI auf GPIO10**. Ein Umverdrahten der Platine
  ist dafür nicht vorgesehen.

Für beide LED-Aufbauten stehen Farbe, Helligkeit, Rainbow, Atmen, Blinken und Aus
zur Verfügung. Bei der Zubereitung blinkt die Beleuchtung rot; nach Abschluss
leuchtet sie fünf Sekunden grün. Es ist jeweils ein LED-Aufbau aktiv.

## Prüfung dieser Änderung

Automatisierte Backendtests prüfen Standardwerte, Speichern und Wiederherstellen,
beide Pumpenpolaritäten, Abschalten bei Fehlern, Sperre während eines Auftrags,
fehlenden PIO-Treiber sowie Ring-Farbfolge und Animationen:

```bash
python -m unittest discover -s raspberry -p 'test_*.py' -v
```

Ein tatsächlicher Funktionstest am Raspberry Pi und am LED-Ring ist zusätzlich
erforderlich; auf dem Entwicklungsrechner werden GPIO und LEDs simuliert.

Treibergrundlage: [Adafruit – NeoPixels auf Pi 5](https://learn.adafruit.com/circuitpython-on-raspberrypi-linux/using-neopixels-on-the-pi-5).
