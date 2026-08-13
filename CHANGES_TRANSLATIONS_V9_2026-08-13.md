# CocktailBot V9 – Übersetzungen Einstellungen

Datum: 13.08.2026

## Behoben

- Fehlende Übersetzungen auf der Einstellungen-Übersicht ergänzt.
- Neue Bereiche wie Gewerbelizenz, PayPal-Kassenmodus, Cocktailpreise, Branding, Partykarten, Partyplaner, Einkaufsliste sowie Sicherheit/Freigaben in die Übersetzungslogik aufgenommen.
- App-schließen-Dialog und Raspberry-Verbindungsstatus übersetzt.
- Gewerbelizenz-Status wird jetzt mit der aktuell gewählten App-Sprache ausgegeben.
- Lizenzmeldungen werden vor der Anzeige durch die Übersetzungsfunktion geführt.
- PayPal-Backend-Statusmeldungen werden übersetzt.
- Zutaten-löschen-Dialoge wurden aus fest codiertem Deutsch auf lokalisierte Texte umgestellt.
- LED-Statusmeldungen und Pumpen-Fortschrittstexte wurden lokalisiert.
- Anzeige-Hinweis von alter Seiten-Navigation auf die aktuelle obere Navigation korrigiert.

## Fallback-Verhalten

Bei einer Nicht-Deutsch-Sprache wird ein neuer UI-Text ohne eigene Sprachvariante nicht mehr still auf den deutschen Schlüssel zurückgesetzt. Für solche seltenen Texte wird mindestens eine englische Übersetzung verwendet. Dadurch bleiben neue Einstellungsfunktionen nicht mehr teilweise deutsch.

## Prüfung

- Alle statischen `tr(...)`, `store.t(...)`, `widget.store.t(...)` und `T(...)`-Texte im Einstellungsbereich wurden gegen die vorhandenen Übersetzungen bzw. den neuen Fallback geprüft.
- Ergebnis: keine statischen deutschen UI-Schlüssel im Einstellungsbereich ohne Übersetzung/Fallback.
- `bash -n install.sh`: OK
- `bash -n raspberry/start-kiosk.sh`: OK
- `python3 -m py_compile raspberry/cocktailbot_server.py`: OK
- Flutter SDK ist in der Arbeitsumgebung nicht installiert; daher kein vollständiger Flutter-Web-Build lokal durchgeführt.
