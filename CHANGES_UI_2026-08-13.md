# Änderungen 2026-08-13 – UI, Bilder, Bildschirmtastatur

## Flutter-App (`app/lib/main.dart`)

- Linke Seitenleiste auf Landscape-/Tablet-Ansichten weiter nach oben gezogen.
- Padding im linken Navigationsbereich reduziert.
- Cocktail-Detailseite: großes Bild jetzt mit `BoxFit.contain` statt Beschnitt.
- Cocktail-Detailbild reagiert jetzt auf kleine 1024x600-Displays mit reduzierter Hero-Höhe.

## Kiosk / Raspberry (`raspberry/start-kiosk.sh`)

- Chromium startet zusätzlich mit:
  - `--touch-events=enabled`
  - `--enable-features=VirtualKeyboard`

## Installer (`install.sh`)

- Installiert jetzt zusätzlich `onboard` und `dbus-x11`.
- Legt `start-onboard.sh` an und startet die Bildschirmtastatur automatisch im Desktop-Autostart.
- Versucht Auto-Show für Onboard per `gsettings` zu aktivieren.
- Damit sollen Eingabefelder auf dem Touchdisplay besser bedienbar sein (z. B. Kalibrierung, Preise, Zutaten, Lizenz, Rezepte).

## App schließen / Desktop

- Unter **Einstellungen** gibt es unten einen roten Button **App schließen**.
- Vor dem Beenden erscheint eine Sicherheitsabfrage.
- Der lokale Raspberry-Endpunkt `POST /api/kiosk/exit` stoppt laufende Pumpen, setzt ein Kiosk-Exit-Signal und beendet nur den CocktailBot-Chromium-Prozess.
- `start-kiosk.sh` erkennt den absichtlichen Exit und startet Chromium in derselben Sitzung nicht sofort wieder.
- Beim nächsten normalen Desktop-Autostart/Neustart wird das Exit-Signal zurückgesetzt und CocktailBot startet wieder automatisch.
- Der Installer legt auf dem Desktop **CocktailBot starten** an. Damit kann der Kiosk nach einem manuellen Schließen sofort wieder gestartet werden.
