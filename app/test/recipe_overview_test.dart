import 'package:cocktailbot_app/main.dart';
import 'package:cocktailbot_app/drink_previews.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  test('previews apply only when requested', () {
    final original = drinkPreviews.keys.first;
    final preview =
        cocktailImage(original, fallbackAsset: original, preview: true)
            as Image;
    final detail = cocktailImage(original, fallbackAsset: original) as Image;
    expect(
      (((preview.image as ResizeImage).imageProvider) as AssetImage).assetName,
      drinkPreviews[original],
    );
    expect(
      (((detail.image as ResizeImage).imageProvider) as AssetImage).assetName,
      original,
    );
  });
  for (final size in [const Size(1024, 600), const Size(390, 844)]) {
    testWidgets('bottom pagination navigates and resets scroll at $size', (
      tester,
    ) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final store = MachineStore()..cocktailsPerPage = 8;
      store.recipes.addAll(
        List.generate(
          24,
          (i) => Recipe(
            id: 'test-$i',
            name: 'Cocktail $i',
            description: '',
            category: DrinkCategory.cocktail,
            parts: [],
          ),
        ),
      );
      expect(
        store.sortedRecipesForCategory(DrinkCategory.cocktail).length,
        greaterThan(8),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: RecipeOverview(
              store: store,
              category: DrinkCategory.cocktail,
              title: 'Cocktails',
              onOpenRecipe: (_, __) {},
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final footer = find.byKey(const ValueKey('recipe-pages-bottom'));
      await tester.scrollUntilVisible(footer, 300);
      await tester.pumpAndSettle();
      Finder button(String tooltip) => find.descendant(
        of: footer,
        matching: find.byWidgetPredicate(
          (w) => w is IconButton && w.tooltip == tooltip,
        ),
      );
      expect(
        tester.widget<IconButton>(button('Vorherige Seite')).onPressed,
        isNull,
      );
      await tester.ensureVisible(button('Nächste Seite'));
      await tester.tap(button('Nächste Seite'));
      await tester.pumpAndSettle();
      final scroll = tester.widget<CustomScrollView>(
        find.byType(CustomScrollView),
      );
      expect(scroll.controller!.offset, 0);
      await tester.scrollUntilVisible(footer, 300);
      await tester.pumpAndSettle();
      expect(
        tester.widget<IconButton>(button('Vorherige Seite')).onPressed,
        isNotNull,
      );
      await tester.ensureVisible(button('Vorherige Seite'));
      await tester.tap(button('Vorherige Seite'));
      await tester.pumpAndSettle();
      expect(scroll.controller!.offset, 0);
      await tester.pumpWidget(const SizedBox());
      store.dispose();
    });
  }
}
