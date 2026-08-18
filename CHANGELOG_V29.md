## V29 – LAN-/Tablet-Zugriff mit Admin-PIN (17.08.2026)

- Neuer Bereich **Einstellungen → Netzwerk & Tablet**.
- CocktailBot kann dort gezielt für Geräte im **gleichen lokalen WLAN/LAN** freigegeben oder wieder gesperrt werden.
- Der Raspberry-Dienst lauscht technisch auf `0.0.0.0:8080`, blockiert externe Geräte aber serverseitig, solange der LAN-Zugriff nicht ausdrücklich aktiviert wurde.
- Öffentliche Internet-IP-Adressen werden vom Backend grundsätzlich abgewiesen; die Freigabe ist nur für private/lokale Netze vorgesehen.
- Beim Aktivieren muss ein **4- bis 8-stelliger Admin-PIN** gesetzt werden. Der PIN wird auf dem Raspberry nur als PBKDF2-Hash mit zufälligem Salt gespeichert.
- Tablet/PC können Cocktails ohne Admin-PIN auswählen und zubereiten; der Einstellungsbereich fordert auf externen Geräten immer den Admin-PIN an.
- Kritische Remote-Aktionen wie Kalibrierung/Pumpenlauf, Reinigung, Priming, LED-Konfiguration, Lizenzänderungen, PayPal-Konfiguration, Bildverwaltung und Kiosk-Beenden sind zusätzlich serverseitig durch eine zeitlich begrenzte Admin-Sitzung geschützt.
- Die Netzwerkseite zeigt automatisch erkannte Raspberry-IP-Adressen als direkt nutzbare URLs wie `http://192.168.x.x:8080` an und bietet Kopieren per Touch.
- Der Raspberry veröffentlicht einen bereinigten App-Zustand für LAN-Geräte, damit Rezepte, aktive Größen, Designs, Preise, Party-/Statistikdaten und weitere nicht geheime Einstellungen auf dem Tablet übernommen werden.
- Einstellungs-Passwort und Lizenzcode werden nicht in den LAN-App-Zustand aufgenommen.
- Zubereitungen von einem Tablet synchronisieren Füllstände direkt zurück zum Raspberry; Verbrauchsereignisse werden für die zentrale Statistik im Raspberry-App-Zustand nachgeführt und gegen doppelte Übertragung dedupliziert.
- Die Statistik lädt beim Öffnen den aktuellen gemeinsamen Zustand; die Füllstandsseite aktualisiert die Pumpenzustände vom Raspberry.
- Der lokale Kiosk bleibt unverändert auf `http://127.0.0.1:8080` und funktioniert auch bei deaktiviertem LAN-Zugriff.


### Ergänzung – Lizenz- und Nutzungshinweis (18.08.2026)

- Neuer Bereich **Einstellungen → Info & Lizenz** mit Copyright, Kontakt zu Sascha Wenning / Printcore und den Nutzungsbedingungen für Privat- und Gewerbebetrieb.
- Beim Start erscheint ein nicht wegklickbarer Lizenz- und Nutzungshinweis, solange der Nutzer ihn nicht mit **„Akzeptieren“** bestätigt hat.
- Optional kann **„Diesen Hinweis nicht mehr anzeigen“** aktiviert werden; die Bestätigung wird versionsgebunden in den lokalen App-Einstellungen gespeichert.
- Über **Info & Lizenz → Start-Hinweis wieder anzeigen** kann die gespeicherte Ausblendung jederzeit zurückgesetzt werden.
- **„Ablehnen“** beendet am Raspberry den Chromium-Kiosk über den vorhandenen sicheren Kiosk-Exit-Endpunkt. Auf einem entfernten Tablet/PC wird nur die dortige Sitzung gesperrt, damit ein Remote-Nutzer nicht den Raspberry-Kiosk abschalten kann.
