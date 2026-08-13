# LED-Firmware: nicht blockierende Effekte

Datum: 2026-08-13

## Behoben

- `RAINBOW` blockiert die USB-Serial-Verarbeitung nicht mehr.
- `BLINK 255 0 0` unterbricht einen laufenden Rainbow-Effekt sofort.
- `PULSE`, `BLINK`, `BUSY` und `ERROR` laufen als nicht blockierende Zustandsmaschine.
- `BUSY` und `ERROR` funktionieren jetzt korrekt; die alte Blink-Funktion akzeptierte intern nur `current_mode == "BLINK"`.
- Rainbow wendet die globale `BRIGHT`-Einstellung jetzt ebenfalls an.
- Neue Befehle werden vor jedem Animations-Frame abgearbeitet.
- `STATUS` wurde als Diagnosebefehl ergänzt.

## Maschinenablauf

Der Raspberry-Server verwendet weiterhin:

- Idle: gewählter LED-Effekt
- Zubereitung: `BLINK 255 0 0`
- Erfolgreich: `READY` (grün), danach nach 5 Sekunden zurück zum Idle-Effekt
- Fehler: `ERROR`, danach zurück zum Idle-Effekt

Die Raspberry-Serverlogik musste hierfür nicht geändert werden; der Fehler lag in der blockierenden Pico-Firmware.
