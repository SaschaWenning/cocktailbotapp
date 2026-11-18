# CocktailBot 2.8 – Hauptseiten-Tabs, Pumpensteuerung und Beleuchtung

## Reparatur nach fehlgeschlagenem Update / vollem Datenträger

Wenn der Quellcode schon aktualisiert wurde, kann die alte Update-Prüfung trotzdem
fälschlich „aktuell“ melden, obwohl der Flutter-Build abgebrochen ist. Die
korrigierte Version bestätigt eine Installation erst nach erfolgreichem
Web-/Backend-Update und speichert Prüfsummen der tatsächlich installierten Dateien.
Die Update-Seite zeigt außerdem den Arbeitsschritt und das Fehlerprotokoll.

Zuerst alle Dateien dieses Updatepakets in ihrer bestehenden Ordnerstruktur auf
GitHub hochladen. Unter GitHub → Actions auf den erfolgreichen Abschluss von
**Build Flutter Web** für diesen Commit warten. Danach am Raspberry Pi einmal:

```bash
curl -fsSL https://raw.githubusercontent.com/SaschaWenning/cocktailbotapp/main/tools/repair-update.sh -o /tmp/cocktailbot-repair-update.sh
sudo bash /tmp/cocktailbot-repair-update.sh
```

Die Reparatur stoppt die Pumpen, entfernt ausschließlich generierte Flutter-Build-
und Paketcachedateien und lädt die korrigierten Installationsskripte. Sie ersetzt
lokale Änderungen im Quellordner durch GitHub `main`; Rezepte und Einstellungen
in `/var/lib/cocktailbot` bleiben erhalten. Danach installiert sie den geprüften,
fertig gebauten Web-Release und startet nur bei Erfolg neu. Die Ausgabe im
Terminal zeigt dabei den Fortschritt. Bei weniger als 512 MiB freiem Speicher
prüft das Update automatisch, ob das ext4-Systemdateisystem kleiner als seine
vorhandene Partition ist. In diesem Fall wird es mit `resize2fs` online vergrößert
und das Update anschließend fortgesetzt. Sobald die neuen Dateien auf GitHub
liegen, funktioniert das über den Updateknopf ohne eigenen Terminalbefehl.

Die Automatik verändert keine Partitionstabelle. Bei tatsächlich vollem
Datenträger, anderen Dateisystemen oder fehlgeschlagener Erweiterung bricht das
Update weiterhin mit einer konkreten Fehlermeldung ab. Bei bereits genügend
freiem Platz wird nichts vergrößert. Der Schritt wird im Update-Protokoll und in
der Fortschrittsanzeige gemeldet.

Künftige Updates verwenden den passenden fertigen Web-Release statt eines lokalen
Flutter-Builds auf dem Pi. Ein nicht passender oder fehlender Web-Release wird
abgewiesen; die GitHub-Aktion muss zuerst erfolgreich sein.

## Hardwareauswahl

### Pumpenfehler „Cannot determine SOC peripheral base address“

Diese Meldung entsteht durch die ursprüngliche, zum Pi 5 inkompatible Bibliothek
`RPi.GPIO`. Eine alte Kopie in `/opt/cocktailbot/venv` kann das korrekte Systempaket
verdecken. Der Installer ersetzt sie jetzt ausdrücklich in der App-Umgebung und
prüft den geladenen Treiber, ohne einen Ausgang anzusteuern.

Eine vorhandene Installation kann ohne erneuten Web-Build repariert werden:

```bash
sudo systemctl stop cocktailbot.service
sudo apt-get update
sudo apt-get install -y python3-lgpio python3-rpi-lgpio
sudo /usr/bin/python3 -m venv --system-site-packages /opt/cocktailbot/venv
sudo /opt/cocktailbot/venv/bin/python -m pip uninstall -y RPi.GPIO
sudo /opt/cocktailbot/venv/bin/python -m pip install --no-cache-dir --force-reinstall --no-deps 'rpi-lgpio>=0.6,<1'
/opt/cocktailbot/venv/bin/python -c 'import RPi.GPIO as GPIO, lgpio; print(GPIO.__file__); print(lgpio.__file__)'
sudo systemctl start cocktailbot.service
```

Falls die Paketinstallation fehlschlägt, zuerst deren Fehlermeldung prüfen, bevor
die Pumpe erneut getestet wird. Nach erfolgreicher Reparatur den Fünf-Sekunden-
Test für Pumpe 1 wiederholen. Die MOSFET-Auswahl bleibt gespeichert.

Es gibt zwei unabhängige Auswahlen an den passenden Stellen:

- Oben unter **Einstellungen → Kalibrierung**: **Relais – bisheriger Aufbau** oder **MOSFET-Platine – Cocktailbot V2**.
- Unter **Einstellungen → LED-Beleuchtung**: **Pico 2 – bisherige 240 LEDs**, **24-LED-Ring – über die Platine** oder **240 LEDs – über die Platine**.

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

## 24 oder 240 LEDs an der V2-Platine

- WS2812B mit wahlweise 24 oder 240 LEDs, Daten über **BCM9 / physischen Pin 21**.
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

Bei **240 LEDs über die Platine** eine ausreichend dimensionierte externe
5-V-Versorgung für die LEDs verwenden. LED-Plus kommt direkt an diese Versorgung;
DATA und GND werden mit der Platine verbunden. Der +5-V-Pin der LED-Buchse auf
der Platine bleibt dabei frei. Die Stromtragfähigkeit des kleinen Step-downs und
des Platinenanschlusses ist für 240 LEDs nicht nachgewiesen. Ein zusätzlicher
5-V-Step-down kann aus derselben 12-V-Hauptversorgung gespeist werden, sofern
deren Gesamtleistung ausreicht.

Für alle drei LED-Aufbauten stehen Farbe, Helligkeit, Rainbow, Atmen, Blinken und Aus
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
