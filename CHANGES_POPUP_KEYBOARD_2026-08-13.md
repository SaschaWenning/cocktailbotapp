# CocktailBot – In-App Popup-Tastatur (13.08.2026)

## Neue Bildschirmtastatur

Die Flutter-App verwendet jetzt eine eigene Bildschirmtastatur als Popup. Dadurch ist die Eingabe im Raspberry-Pi-Kiosk nicht mehr davon abhängig, ob LXDE/X11 oder Onboard ein Flutter-Web-Eingabefeld korrekt erkennt.

- Tippen auf ein editierbares `TextField` oder `TextFormField` öffnet das Popup automatisch.
- Zahlenfelder (z. B. Behältergröße, Füllstand, Kalibrierwerte, Preise) erhalten einen großen Nummernblock.
- Textfelder erhalten eine QWERTZ-Tastatur mit `Ä`, `Ö`, `Ü`, Shift, Leerzeichen, Enter, Löschen und Rücktaste.
- `Fertig` löst vorhandene `onSubmitted`-Logik des aktiven Eingabefelds aus und schließt die Tastatur.
- Eingaben werden als echte Flutter-Benutzereingabe an `EditableText` übergeben, damit vorhandene Input-Formatter und `onChanged`-Logik weiter greifen.
- Das Popup liegt nur im unteren Bildschirmbereich über der App; die obere Navigation bleibt sichtbar.

## Raspberry / Onboard

Onboard bleibt als manuelle Fallback-Option im System, wird vom CocktailBot-Installer aber nicht mehr automatisch gestartet. Ein alter CocktailBot-Onboard-Autostart wird beim Update entfernt, damit nicht zwei Bildschirmtastaturen gleichzeitig erscheinen.

## Navigation

Die zuvor umgestellte horizontale Navigation im 1024x600-Querformat bleibt unverändert erhalten.
