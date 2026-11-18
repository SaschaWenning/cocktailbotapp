import 'dart:async';

/// Serialize writes and combine rapid requests into a snapshot of the latest state.
class CoalescedSaveQueue {
  CoalescedSaveQueue(
    this.write, {
    this.delay = const Duration(milliseconds: 60),
  });
  final Future<void> Function() write;
  final Duration delay;
  Timer? _timer;
  bool _running = false;
  bool _dirty = false;
  List<Completer<void>> _waiters = [];

  Future<void> request({bool immediate = false}) {
    final waiter = Completer<void>();
    _waiters.add(waiter);
    _dirty = true;
    _timer?.cancel();
    if (immediate) {
      unawaited(_drain());
    } else {
      _timer = Timer(delay, _drain);
    }
    return waiter.future;
  }

  Future<void> flush() =>
      _dirty || _running ? request(immediate: true) : Future<void>.value();

  Future<void> _drain() async {
    if (_running) return;
    _timer?.cancel();
    _running = true;
    try {
      while (_dirty) {
        _dirty = false;
        final batch = _waiters;
        _waiters = [];
        try {
          await write();
          for (final waiter in batch) {
            waiter.complete();
          }
        } catch (error, stack) {
          for (final waiter in batch) {
            waiter.completeError(error, stack);
          }
        }
      }
    } finally {
      _timer?.cancel();
      _running = false;
    }
  }
}
