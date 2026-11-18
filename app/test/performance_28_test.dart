import 'dart:async';
import 'dart:convert';
import 'package:cocktailbot_app/coalesced_save.dart';
import 'package:cocktailbot_app/image_bytes_cache.dart';
import 'package:cocktailbot_app/job_result.dart';
import 'package:cocktailbot_app/main.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('rapid saves write one latest snapshot', () async {
    var value = 0;
    final writes = <int>[];
    final queue = CoalescedSaveQueue(() async {
      writes.add(value);
    });
    final pending = <Future<void>>[];
    for (var i = 1; i <= 4; i++) {
      value = i;
      pending.add(queue.request());
    }
    await Future.wait(pending);
    expect(writes, [4]);
  });

  test(
    'save during a write is serialized and persists the latest state',
    () async {
      final gate = Completer<void>();
      var value = 1;
      var active = 0;
      var maxActive = 0;
      final writes = <int>[];
      final queue = CoalescedSaveQueue(() async {
        active++;
        if (active > maxActive) maxActive = active;
        writes.add(value);
        if (writes.length == 1) await gate.future;
        active--;
      });
      final first = queue.request(immediate: true);
      value = 2;
      final second = queue.request();
      value = 3;
      final third = queue.request();
      gate.complete();
      await Future.wait([first, second, third]);
      expect(writes, [1, 3]);
      expect(maxActive, 1);
    },
  );

  test('save queue recovers after a failed write', () async {
    var fail = true;
    final queue = CoalescedSaveQueue(() async {
      if (fail) throw StateError('disk full');
    });
    await expectLater(queue.request(), throwsStateError);
    fail = false;
    await queue.request();
  });

  test('embedded image decoding reuses bytes and has bounded eviction', () {
    final cache = ImageBytesCache(maxBytes: 6, maxEntries: 2);
    String image(int number) =>
        'data:image/png;base64,${base64Encode([number, number, number])}';
    final a = cache.decode(image(1));
    expect(identical(a, cache.decode(image(1))), isTrue);
    cache.decode(image(2));
    cache.decode(image(3));
    expect(identical(a, cache.decode(image(1))), isFalse);
  });

  test('idle alone and another job never count as successful completion', () {
    expect(
      () => jobCompletedSuccessfully({'busy': false}, 'a'),
      throwsException,
    );
    expect(
      () => jobCompletedSuccessfully({
        'jobId': 'b',
        'jobState': 'succeeded',
      }, 'a'),
      throwsException,
    );
    expect(
      () => jobCompletedSuccessfully({
        'jobId': 'a',
        'jobState': 'cancelled',
      }, 'a'),
      throwsException,
    );
    expect(
      jobCompletedSuccessfully({'jobId': 'a', 'jobState': 'succeeded'}, 'a'),
      isTrue,
    );
  });

  test(
    'unchanged status polls do not rebuild the global store listeners',
    () async {
      final store = MachineStore(
        client: MockClient(
          (request) async =>
              http.Response(jsonEncode({'ok': true, 'busy': false}), 200),
        ),
      );
      var notifications = 0;
      store.addListener(() => notifications++);
      await store.fetchMachineStatus(compact: true);
      await store.fetchMachineStatus(compact: true);
      await store.fetchMachineStatus(compact: true);
      expect(notifications, 1);
      store.dispose();
    },
  );

  test(
    'shared state sends only changed fields after the first synchronization',
    () async {
      final patches = <Map<String, dynamic>>[];
      final store = MachineStore(
        client: MockClient((request) async {
          if (request.url.path == '/api/app-state/patch')
            patches.add(jsonDecode(request.body));
          return http.Response('{"ok":true}', 200);
        }),
      )..connected = true;
      await store.save();
      await store.flushSaves();
      store.darkMode = false;
      await store.save();
      await store.flushSaves();
      expect(patches.length, 2);
      expect((patches.last['changes'] as Map).keys, ['darkMode']);
      expect(patches.last['removed'], isEmpty);
      store.dispose();
    },
  );

  for (final state in ['failed', 'cancelled', 'succeeded']) {
    test(
      'recipe books consumption only after explicit success ($state)',
      () async {
        final store = MachineStore(
          client: MockClient((request) async {
            if (request.url.path == '/api/command') {
              final command = jsonDecode(request.body);
              if (command['action'] == 'prepare_recipe') {
                return http.Response(
                  '{"ok":true,"accepted":true,"jobId":"job-a"}',
                  202,
                );
              }
            }
            if (request.url.path == '/api/jobs/job-a') {
              return http.Response(
                jsonEncode({
                  'jobId': 'job-a',
                  'jobState': state,
                  'jobError': 'GPIO test',
                  'busy': false,
                  'activePumps': [],
                  'progress': 1,
                }),
                200,
              );
            }
            return http.Response('{"ok":true}', 200);
          }),
        )..connected = true;
        store.pumps.first.mlPerSecond = 10;
        store.pumps.first.remainingMl = 500;
        final recipe = Recipe(
          id: 'test-drink',
          name: 'Test',
          description: '',
          category: DrinkCategory.cocktail,
          baseVolumeMl: 50,
          parts: [
            RecipePart(ingredientId: 'dark-rum', amountMl: 50, automatic: true),
          ],
        );
        if (state == 'succeeded') {
          await store.makeRecipe(recipe, targetVolumeMl: 50);
          expect(store.pumps.first.remainingMl, 450);
          expect(store.consumptionHistory.length, 1);
        } else {
          await expectLater(
            store.makeRecipe(recipe, targetVolumeMl: 50),
            throwsException,
          );
          expect(store.pumps.first.remainingMl, 500);
          expect(store.consumptionHistory, isEmpty);
          expect(store.recipeDrinkCounts, isEmpty);
        }
        await store.flushSaves();
        store.dispose();
      },
    );
  }
}
