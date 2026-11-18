# CocktailBot 2.8.1

- Übersicht verwendet 400-Pixel-WebP-Vorschaubilder für alle 61 mitgelieferten Getränkebilder (zusammen ca. 1,3 MB statt 121,5 MB).
- Detailansicht behält Originalbilder. Selbst importierte Bilder werden nicht verändert.
- Vorherige/nächste Seite auch unter dem Cocktailraster; Seitenwechsel setzt die Scrollposition zurück.
- Vorschauen sind mit `tools/generate-drink-thumbnails.py` (Pillow) reproduzierbar.

Alle Dateien einschließlich `app/assets/drink_previews/` und `app/lib/drink_previews.dart` hochladen. Anschließend auf erfolgreichen GitHub-Workflow „Build Flutter Web“ warten und App-Update starten.
