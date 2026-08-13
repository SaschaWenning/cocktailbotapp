# CocktailBot – Lizenzdatei-Import

Stand: 13.08.2026

## Änderung

Der bestehende private Windows-Lizenzgenerator bleibt unverändert. Seine Funktion **Als TXT speichern** erzeugt bereits eine Datei mit Geräte-ID und dem Ed25519-signierten `CBL1-...` Lizenzcode.

Die CocktailBot-App verwendet für die Aktivierung jetzt primär einen Dateiimport:

1. Kunde sendet seine Geräte-ID an den Anbieter.
2. Anbieter erzeugt die Gewerbelizenz mit dem bestehenden Generator und speichert sie als TXT.
3. Kunde erhält die TXT-Datei, z. B. per E-Mail oder USB-Stick.
4. Unter **Einstellungen → Gewerbelizenz → Lizenzdatei importieren** wird die Datei ausgewählt.
5. Die Flutter-App liest ausschließlich den signierten `CBL1-...` Code aus der Datei.
6. Der lokale Raspberry-Server prüft Ed25519-Signatur und Hardware-Geräte-ID.
7. Nur bei erfolgreicher Prüfung speichert der Server die aktivierte Lizenz unter `/var/lib/cocktailbot/license.json` mit Modus `0600`.

Der Kunde muss weder den langen Lizenzcode eingeben noch Dateien manuell in geschützte Linux-Verzeichnisse kopieren.

## Dateiauswahl

Flutter Web nutzt `file_picker` 11.0.2. Akzeptiert werden TXT-Dateien bis 64 KiB. Der Import versteht sowohl die vom bestehenden Generator erzeugte Zeile `Lizenzcode: CBL1-...` als auch eine Datei, die nur den `CBL1-...` Code enthält.

## Sicherheit

Der private Ed25519-Schlüssel bleibt ausschließlich im privaten Lizenzgenerator. Das öffentliche Raspberry-Paket enthält weiterhin nur den öffentlichen Prüfschlüssel. Eine für Raspberry A ausgestellte TXT-Datei wird auf Raspberry B wegen der abweichenden Geräte-ID abgelehnt.
