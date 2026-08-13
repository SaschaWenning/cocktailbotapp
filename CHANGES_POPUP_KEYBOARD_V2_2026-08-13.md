# Popup-Tastatur V2 – 13.08.2026

## Behoben

- Die Popup-Tastatur besitzt jetzt oberhalb der Tasten ein eigenes Eingabefenster.
  Dadurch bleibt der aktuell eingegebene Wert sichtbar, auch wenn die Tastatur das
  eigentliche Formularfeld überdeckt.
- Die virtuelle Tastatur führt einen eigenen `TextEditingValue` als Eingabepuffer.
  Nach jedem Tastendruck wird die Textauswahl explizit auf eine Cursorposition
  zusammengeklappt. Dadurch ersetzt die nächste Zahl bzw. der nächste Buchstabe
  nicht mehr den bereits eingegebenen Wert.
- Auch die `TextEditingController.selection` des aktiven Flutter-Feldes wird nach
  jedem virtuellen Tastendruck auf den Cursor gesetzt. Das verhindert, dass eine
  Chromium/Flutter-Web-Selektion optisch markiert bleibt.
- InputFormatter bleiben aktiv, weil Änderungen weiterhin über
  `EditableTextState.userUpdateTextEditingValue(...)` als Benutzereingabe
  weitergegeben werden.
- Das Eingabefenster zeigt einen Cursor und bei Passwortfeldern nur Punkte an.
- Nummernblock und QWERTZ-Tastatur bleiben automatisch vom Typ des fokussierten
  Eingabefeldes abhängig.

## Raspberry/Kiosk

Keine Änderung an GPIO, Pumpen, Pico, PayPal oder Display-Konfiguration.
Die bestehende horizontale Navigation im 1024x600-Querformat bleibt erhalten.
