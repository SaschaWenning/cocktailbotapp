# CocktailBot Update – Cocktailkarte & Bildschirmtastatur (13.08.2026)

## Cocktailkarte 1024x600

- Die linke Navigation ist auf Tablet/Kiosk fest am linken Rand und beginnt direkt oben.
- Die Cocktail-Detailseite behält dieselbe feste Navigation bei.
- Auf 1024x600 wird die Detailseite zweispaltig dargestellt:
  - links Cocktailbild mit `BoxFit.contain` und Zubereiten-Button darunter,
  - rechts Beschreibung, Zielgröße, Alkoholinformationen, Warnungen und Zutaten.
- Zurück-Button und Cocktailname liegen kompakt oberhalb der beiden Spalten.

## Bildschirmtastatur

- `onboard`, `dbus-x11` und `dconf-cli` werden vom Installer installiert.
- Onboard wird beim Desktop-Login gestartet und für Auto-Show konfiguriert.
- Zusätzlich erkennt die Flutter-App den Fokus auf allen `TextField`-/`TextFormField`-Eingaben zentral.
- Bei Fokus ruft Flutter `/api/keyboard/show` auf; der Raspberry-Dienst zeigt Onboard explizit per D-Bus an.
- Beim Verlassen eines Eingabefeldes wird `/api/keyboard/hide` aufgerufen.
- Dadurch gilt die Lösung auch für Füllstände, Behältergrößen, Kalibrierwerte, Preise, Passwörter und weitere Eingabefelder.

## Kiosk / Update-Stabilität

- Chromium startet mit deaktiviertem Web-Cache und einer Cache-Buster-URL.
- Flutter-Service-Worker- und Chromium-Web-Caches werden beim Kioskstart entfernt, Local Storage bleibt erhalten.
- Der Flask-Webserver liefert `Cache-Control: no-store`, damit alte 500-Seiten nach Updates nicht hängen bleiben.
- Der Installer korrigiert die Web-Dateirechte nach jedem Web-Update automatisch.
- `App schließen` wird über `/api/kiosk/exit` unterstützt; Chromium bleibt danach aus und der Raspberry-Desktop ist sichtbar.
- Auf dem Desktop wird `CocktailBot starten` angelegt.
- `tools/update.sh` startet den Installer explizit mit `bash` und überspringt LCD-/Boot-Konfiguration.

## Display

- Bei einer vollständigen Neuinstallation wird KMS wieder aktiviert und 1024x600 über `video=HDMI-A-1:1024x600M@60` gesetzt.
- Alte Legacy-HDMI-/Framebuffer-Zwangseinstellungen werden entfernt.

## Validierung

- `bash -n`: Installer, Kioskstart, Onboard-Start und Update-Skript geprüft.
- `python3 -m py_compile`: Raspberry-Server geprüft.
- Dart-Klammer-/Strukturprüfung durchgeführt.
- Ein vollständiger Flutter-Web-Build ist in dieser Arbeitsumgebung nicht verfügbar und muss über den GitHub-Workflow bzw. Flutter erfolgen.
