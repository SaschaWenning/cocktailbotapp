# CocktailBot V11 – Pumpen-Bootschutz

- LOW-aktive Relais (`COCKTAILBOT_ACTIVE_HIGH=0`) sind jetzt der sichere Standard.
- Alle 18 Pumpen-GPIOs werden bei jedem Installieren/Update in `config.txt` bereits im Firmware-/Bootloader-Stadium auf den AUS-Pegel gesetzt.
- Bei LOW-aktiven Relais ist der AUS-Pegel HIGH (`op,dh`); bei `--active-high 1` wird automatisch LOW (`op,dl`) verwendet.
- Die Pumpen-Sicherheitskonfiguration läuft auch bei Updates mit `--skip-boot-opt`; sie ist nicht mehr an die Display-Bootoptimierung gekoppelt.
- GPIO15 wird für Pumpe 18 reserviert. Die Onboard-UART-Konsole wird deaktiviert/aus `cmdline.txt` entfernt, damit Linux GPIO15 beim Start nicht wieder als UART-RX beansprucht.
- Der Pico 2 bleibt unverändert über USB-Serial erreichbar.
- Der Raspberry-Server verwendet auch ohne Environment-Datei LOW-aktive Relais als sicheren Standard und initialisiert alle `OutputDevice`s mit `initial_value=False` (= Pumpe AUS).
- `tools/update.sh` verwendet ebenfalls `active-high=0` als Fallback und übernimmt eine vorhandene Einstellung weiter.

Hinweis: Software kann die Zeit unmittelbar nach dem Anlegen der Versorgung vor Ausführung der Firmware nicht physikalisch garantieren. Für eine absolut glitchfreie Leistungsfreigabe ist zusätzlich ein Hardware-Enable/Pull-up sinnvoll.
