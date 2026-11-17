# CocktailBot 2.7

Unter **Einstellungen → Anzeige → Tabs auf der Hauptseite** lassen sich diese
Tabs ein- und ausblenden:

- Cocktails
- Alkoholfrei
- Shots
- Füllstände

Mit den Pfeilen lässt sich die Reihenfolge der eingeblendeten Tabs ändern.
Änderungen werden sofort gespeichert, in Backups übernommen und mit der
gemeinsamen App-Konfiguration synchronisiert. **Einstellungen** bleibt immer
als letzter Tab erreichbar. **Standard-Tabs wiederherstellen** setzt die
bisherige Ansicht zurück: Cocktails, Alkoholfrei, Shots und Einstellungen.

Beispiel: Shots abwählen und Füllstände aktivieren. Anschließend ist die
vorhandene Füllstandsseite direkt über die Hauptnavigation erreichbar. Die
bisherigen Passwörter, Admin-PINs und Vermietfreigaben gelten weiterhin.
Im Vermietmodus vollständig ausgeblendete Füllstände erscheinen auch nicht
in der Hauptnavigation; bei Service-PIN-Schutz erfolgt weiterhin die PIN-Abfrage.

Beim Wechsel auf Version 2.7 bleibt die bisherige Navigation zunächst erhalten.
Gespeicherte Pumpen- und LED-Auswahlen werden nicht geändert.

## Installation über GitHub

Die Dateien des Updatepakets in ihrer bestehenden Ordnerstruktur auf GitHub
ersetzen. Warten, bis **Build Flutter Web** für den neuen Commit erfolgreich
abgeschlossen ist. Danach das Update am CocktailBot über die App starten.
Die Versionsdatei lautet **2.7**, die Flutter-Version **2.7.0+27**.
