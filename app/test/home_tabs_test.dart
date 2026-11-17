import 'package:cocktailbot_app/home_tabs.dart';
import 'package:cocktailbot_app/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('old installations retain their existing tabs', () {
    expect(normalizeHomeTabs(null), [
      'cocktails',
      'mocktails',
      'shots',
      'settings',
    ]);
  });

  test(
    'saved IDs keep order, discard duplicates and always retain settings',
    () {
      expect(
        normalizeHomeTabs([
          'fill',
          'shots',
          'fill',
          'unknown',
          'settings',
          'cocktails',
        ]),
        ['fill', 'shots', 'cocktails', 'settings'],
      );
      expect(normalizeHomeTabs([]), ['settings']);
    },
  );

  test('visibility and ordering survive store reload', () async {
    final store = MachineStore();
    await store.setHomeTabs(['fill', 'mocktails', 'cocktails']);
    final restored = MachineStore();
    await restored.load(skipConnect: true);
    expect(restored.homeTabs, ['fill', 'mocktails', 'cocktails', 'settings']);
    expect(restored.visibleHomeTabs, isNot(contains('shots')));
  });

  testWidgets('display settings can replace Shots with fill levels', (
    tester,
  ) async {
    final store = MachineStore();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: HomeTabsSettingsCard(store: store),
          ),
        ),
      ),
    );
    await tester.tap(
      find.descendant(
        of: find.byKey(const ValueKey('home-tab-shots')),
        matching: find.byType(Checkbox),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(
      find.descendant(
        of: find.byKey(const ValueKey('home-tab-fill')),
        matching: find.byType(Checkbox),
      ),
    );
    await tester.pumpAndSettle();
    expect(store.homeTabs, ['cocktails', 'mocktails', 'fill', 'settings']);
    await tester.tap(
      find.descendant(
        of: find.byKey(const ValueKey('home-tab-fill')),
        matching: find.byTooltip('Nach oben'),
      ),
    );
    await tester.pumpAndSettle();
    expect(store.homeTabs, ['cocktails', 'fill', 'mocktails', 'settings']);
    await tester.ensureVisible(find.text('Standard-Tabs wiederherstellen'));
    await tester.tap(find.text('Standard-Tabs wiederherstellen'));
    await tester.pumpAndSettle();
    expect(store.homeTabs, defaultHomeTabs);
  });

  testWidgets('fill-level shortcut preserves the settings password gate', (
    tester,
  ) async {
    final store = MachineStore()
      ..homeTabs = ['fill', 'settings']
      ..settingsLockEnabled = true
      ..settingsPassword = 'secret';
    await tester.pumpWidget(MaterialApp(home: HomeShell(store: store)));
    await tester.pumpAndSettle();
    expect(find.text('Einstellungen gesperrt'), findsWidgets);
    expect(find.byType(FillLevelsPage), findsNothing);
    expect(cocktailBotNavigationItems(store).map((item) => item.$3), [
      'Füllstände',
      'Einstellungen',
    ]);
  });

  testWidgets('unlocked shortcut displays the real fill-level page', (
    tester,
  ) async {
    final store = MachineStore()..homeTabs = ['fill', 'settings'];
    await tester.pumpWidget(MaterialApp(home: HomeShell(store: store)));
    await tester.pumpAndSettle();
    expect(find.byType(FillLevelsPage), findsOneWidget);
  });

  test(
    'hidden rental fill levels cannot be exposed through a configured tab',
    () {
      final store = MachineStore()
        ..homeTabs = ['fill', 'cocktails', 'settings']
        ..commercialLicenseActive = true
        ..rentalModeEnabled = true;
      store.rentalSettingAccess['fill'] = RentalSettingAccess.hidden;
      expect(store.visibleHomeTabs, ['cocktails', 'settings']);
    },
  );

  for (final size in [const Size(1024, 600), const Size(390, 844)]) {
    testWidgets(
      'navigation keeps page IDs after hiding and reordering at $size',
      (tester) async {
        tester.view.physicalSize = size;
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final store = MachineStore()
          ..homeTabs = ['cocktails', 'fill', 'mocktails', 'shots', 'settings'];
        await tester.pumpWidget(
          MaterialApp(
            home: AnimatedBuilder(
              animation: store,
              builder: (context, _) => HomeShell(store: store),
            ),
          ),
        );
        await tester.pumpAndSettle();
        await tester.tap(find.text('Shots').last);
        await tester.pumpAndSettle();
        expect(
          tester.widget<RecipeOverview>(find.byType(RecipeOverview)).category,
          DrinkCategory.shot,
        );
        await store.setHomeTabs(['fill', 'mocktails', 'cocktails']);
        await tester.pumpAndSettle();
        expect(find.byType(FillLevelsPage), findsOneWidget);
        await store.setHomeTabs(['cocktails', 'mocktails', 'fill']);
        await tester.pumpAndSettle();
        expect(find.byType(FillLevelsPage), findsOneWidget);
      },
    );
  }

  testWidgets('rental service PIN still protects the fill-level shortcut', (
    tester,
  ) async {
    final store = MachineStore()
      ..homeTabs = ['fill', 'settings']
      ..commercialLicenseActive = true
      ..rentalModeEnabled = true;
    store.rentalSettingAccess['fill'] = RentalSettingAccess.pinProtected;
    await tester.pumpWidget(MaterialApp(home: HomeShell(store: store)));
    await tester.pumpAndSettle();
    expect(find.text('Mit Service-PIN öffnen'), findsOneWidget);
    expect(find.byType(FillLevelsPage), findsNothing);
  });
}
