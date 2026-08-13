# CocktailBot V10 – einstellbare Füllstandswarnungen

## Neu

- Unter **Einstellungen → Füllstände** gibt es jetzt oben den Bereich **Warnschwellen**.
- **Cocktailkarte orange ab** ist einstellbar von 1 bis 10 Restcocktails.
  - Standard: **2**.
  - Die orange Warnung wird aus der tatsächlich benötigten Rezeptmenge und dem verbleibenden Inhalt der zugeordneten Pumpen berechnet.
- **Füllstandsseite orange unter** ist einstellbar von 5 % bis 90 % in 5-%-Schritten.
  - Standard: **20 %**.
  - Prozentanzeige und Füllbalken werden bei Erreichen der Warnschwelle orange.
- Beide Werte werden dauerhaft in `SharedPreferences` gespeichert und bleiben nach Neustarts/Updates erhalten.
- Die tatsächliche Rezept-Verfügbarkeit bleibt unabhängig von der Warnfarbe: Reicht eine Zutat nicht für die gewählte Rezeptmenge, bleibt der Cocktail nicht verfügbar.
- Neue Texte sind für alle vorhandenen App-Sprachen hinterlegt.

## Standardwerte

- Cocktailkarte: 2 Restcocktails
- Füllstandsseite: 20 %
