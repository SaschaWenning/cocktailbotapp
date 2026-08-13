# CocktailBot – Popup-Tastatur V3

Datum: 13.08.2026

## Behoben

- Langsames Tippen überschreibt nicht mehr den vorherigen Buchstaben bzw. die vorherige Zahl.
- Die Popup-Tastatur hält Text und Cursor jetzt vollständig in einem eigenen lokalen Eingabepuffer.
- Nach dem Öffnen der Popup-Tastatur wird das eigentliche Flutter-/Chromium-Eingabefeld ent-fokussiert. Dadurch kann Chromium nach einer Tipp-Pause keine alte Select-All-Selektion mehr zurückschreiben.
- `requestFocus()` und `userUpdateTextEditingValue()` wurden aus dem virtuellen Tastaturpfad entfernt.
- Werte werden deterministisch direkt über den `TextEditingController` geschrieben.
- Vorhandene `TextInputFormatter` werden weiterhin angewendet.
- `onChanged` wird bei einer tatsächlichen Textänderung weiterhin ausgelöst.
- Die Eingabevorschau im Popup und der Cursor bleiben erhalten.

## Erwartetes Verhalten

Beispiel Zahlenfeld:

1. Feld antippen.
2. Popup öffnet sich.
3. `1` tippen → `1`.
4. Zwei Sekunden warten.
5. `2` tippen → `12`.
6. Zwei Sekunden warten.
7. `5` tippen → `125`.

Dasselbe gilt für Textfelder.

## Unverändert

- Horizontale Navigation oben im 1024×600-Querformat.
- Cocktail-Detailansicht im Querformat.
- Popup-Vorschaufenster.
- Numerische und QWERTZ-Tastatur.
