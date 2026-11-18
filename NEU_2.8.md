# CocktailBot 2.8

## Änderungen

1. Jeder Pumpenauftrag erhält eine eigene ID. Das Backend meldet eindeutig
   `running`, `succeeded`, `failed` oder `cancelled`. Die letzten 64 Aufträge
   bleiben während der Laufzeit abfragbar. Ein schnelles GPIO-Versagen wird
   auch dann erkannt, wenn die erste Abfrage erst danach eintrifft.
   Füllstände und Verbrauch werden bei der Zubereitung nur nach bestätigtem
   Erfolg gebucht. Kalibrierung, Reinigung und Entlüften warten ebenfalls
   auf den tatsächlichen Abschluss ihres Auftrags.
2. Statusabfragen während eines Pumpenlaufs übertragen nur den jeweiligen
   Auftrag. Eine unveränderte Verbindung löst keine erneute globale
   Oberflächen-Benachrichtigung aus. Der normale Abfrageabstand beträgt
   300 ms; Reinigungs- und Entlüftungsanzeigen verwenden 400 ms.
3. Schnelle Speicheränderungen werden für 60 ms gebündelt und anschließend
   nacheinander gespeichert. Die Synchronisation zum Raspberry Pi wird
   ebenfalls gebündelt und übertragen werden nur geänderte Datenbereiche.
   Serverseitige Schreiboperationen laufen geordnet und nutzen eindeutige
   temporäre Dateien mit atomarem Ersetzen. Änderungen an unterschiedlichen
   Bereichen überschreiben sich dadurch nicht mehr als komplette Snapshots.
4. Eingebettete Bilder verwenden einen begrenzten Cache (höchstens 16 MiB
   dekodierte Bytes / 32 Einträge). Vorschaubilder werden mit bis zu 768 Pixeln,
   Detailbilder mit bis zu 1280 Pixeln angefordert. Originaldaten bleiben für
   bestehende Rezepte und Backups erhalten.
5. Die Platinen-LED-Steuerung sendet feste Farben und Aus nur bei Änderung.
   Bei Blinkeffekten werden unveränderte Bilder übersprungen; kontinuierliche
   Animationen werden weiterhin regelmäßig aktualisiert.
6. Chromium darf seinen normalen Datei- und Bildcache wieder verwenden
   (HTTP-Diskcache begrenzt auf 64 MiB). Statische Dateien müssen vor erneuter
   Verwendung ihren ETag prüfen. Geänderte Dateien werden dadurch neu geladen;
   unveränderte können mit HTTP 304 aus dem Cache kommen. HTML, Bootstrap,
   API-Daten und Fehlermeldungen bleiben von Speicherung ausgeschlossen.
   Alte Service-Worker-Caches werden beim Kioskstart weiterhin entfernt.

## Installation

Alle Dateien des Updatepakets mit ihrer Ordnerstruktur auf GitHub ersetzen,
**Build Flutter Web** für den neuen Commit erfolgreich abschließen lassen und
danach über die App aktualisieren. Oberfläche und Backend müssen gemeinsam
auf 2.8 aktualisiert werden. Die bisherigen Tabs, Pumpen- und LED-Auswahlen
bleiben gespeichert. Versionsdatei: **2.8**, Flutter-Version: **2.8.0+28**.

## Grenzen und Prüfung

Ein erfolgreicher Auftrag bestätigt den fehlerfrei abgeschlossenen
Schaltvorgang; ohne Durchflusssensor kann die Software die tatsächlich
geförderte Flüssigkeitsmenge nicht messen. Nach einem teilweise ausgeführten,
abgebrochenen oder unbestätigten Auftrag die Füllstände kontrollieren. Eine
bereits erfolgte Zahlung wird durch diese Änderung nicht automatisch erstattet.
Nach einem Backend-Neustart sind vorherige Auftrags-IDs bewusst nicht mehr
als Erfolg bestätigbar.

Automatisierte Tests prüfen Auftragsfehler, Abbrüche, Verbrauchsbuchungen,
Speicherreihenfolge, Daten-Patches, Cache-Begrenzung, LED-Schreibzugriffe,
Browser-Cache-Erneuerung und die bisherigen Hauptseiten-/Hardwarefunktionen.
Ein messbarer Geschwindigkeitsgewinn am echten Raspberry Pi wurde hier nicht
ermittelt; ein Funktionstest am Gerät steht noch aus.
