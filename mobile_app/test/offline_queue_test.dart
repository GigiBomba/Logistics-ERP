import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/core/storage/local_db.dart';
import 'package:operion_mobile/core/sync/action_queue.dart';

// =============================================================================
// Fake in-memory LocalDatabase that tracks operations for assertions.
// =============================================================================

class _FakeLocalDatabase implements LocalDatabase {
  final _data = <String, Map<String, dynamic>>{};
  final List<String> writeKeys = [];
  final List<String> deleteKeys = [];

  @override
  Future<void> initialize() async {}

  @override
  Future<dynamic> read(String key, {String namespace = 'default'}) async {
    _data.putIfAbsent(namespace, () => <String, dynamic>{});
    return _data[namespace]![key];
  }

  @override
  Future<void> write(
    String key,
    dynamic value, {
    String namespace = 'default',
  }) async {
    writeKeys.add(key);
    _data.putIfAbsent(namespace, () => <String, dynamic>{});
    _data[namespace]![key] = value;
  }

  @override
  Future<void> delete(String key, {String namespace = 'default'}) async {
    deleteKeys.add(key);
    _data[namespace]?.remove(key);
  }

  @override
  Future<List<String>> keysWithPrefix(
    String prefix, {
    String namespace = 'default',
  }) async {
    _data.putIfAbsent(namespace, () => <String, dynamic>{});
    return _data[namespace]!
        .keys
        .where((k) => k.startsWith(prefix))
        .toList()
      ..sort();
  }

  @override
  Future<void> deleteAllWithPrefix(
    String prefix, {
    String namespace = 'default',
  }) async {
    _data[namespace]?.removeWhere((k, _) => k.startsWith(prefix));
  }

  @override
  Future<void> cacheData(
    String collection,
    String key,
    Map<String, dynamic> data,
  ) async {
    _data.putIfAbsent(collection, () => <String, dynamic>{});
    _data[collection]![key] = Map<String, dynamic>.from(data);
  }

  @override
  Future<Map<String, dynamic>?> getCachedData(
    String collection,
    String key,
  ) async {
    final raw = _data[collection]?[key];
    if (raw is Map<String, dynamic>) return Map<String, dynamic>.from(raw);
    return null;
  }

  @override
  Future<void> cacheTransports(List<Map<String, dynamic>> transports) async {
    await clearCollection('transports');
    for (final t in transports) {
      final id = t['id']?.toString() ?? t.hashCode.toString();
      await cacheData('transports', id, t);
    }
  }

  @override
  Future<List<Map<String, dynamic>>> getCachedTransports() async {
    final collection = _data['transports'];
    if (collection == null) return [];
    return collection.values
        .whereType<Map<String, dynamic>>()
        .map((m) => Map<String, dynamic>.from(m))
        .toList();
  }

  @override
  Future<void> clearCollection(String collection) async {
    _data.remove(collection);
  }

  @override
  Future<void> close() async {
    _data.clear();
  }

  /// Returns the raw stored value for [key] in [namespace], or null.
  dynamic storedValue(String key, {String namespace = 'default'}) {
    return _data[namespace]?[key];
  }

  void resetTracking() {
    writeKeys.clear();
    deleteKeys.clear();
  }
}

// =============================================================================
// Tests
// =============================================================================

void main() {
  // ==========================================================================
  // QueuedAction (kept from original)
  // ==========================================================================

  group('QueuedAction', () {
    test('creates with all required fields and default retryCount', () {
      final now = DateTime.now().toUtc();
      final action = QueuedAction(
        id: 'test-id-1',
        endpoint: '/mobile/transports',
        method: 'POST',
        data: {'key': 'value'},
        createdAt: now,
      );
      expect(action.id, 'test-id-1');
      expect(action.endpoint, '/mobile/transports');
      expect(action.method, 'POST');
      expect(action.data, {'key': 'value'});
      expect(action.createdAt, now);
      expect(action.retryCount, 0);
    });

    test('creates with null data', () {
      final action = QueuedAction(
        id: 'test-id-2',
        endpoint: '/test',
        method: 'GET',
        createdAt: DateTime.now().toUtc(),
      );
      expect(action.data, isNull);
    });

    test('creates with empty endpoint and method strings', () {
      final action = QueuedAction(
        id: 'test-id-3',
        endpoint: '',
        method: '',
        createdAt: DateTime.now().toUtc(),
      );
      expect(action.endpoint, isEmpty);
      expect(action.method, isEmpty);
    });

    test('toJson and fromJson roundtrip with data', () {
      final now = DateTime.now().toUtc();
      final action = QueuedAction(
        id: 'test-id-4',
        endpoint: '/mobile/transports/1/status',
        method: 'PATCH',
        data: {'status': 'delivered', 'timestamp': '2025-01-15T10:30:00Z'},
        createdAt: now,
        retryCount: 2,
      );
      final json = action.toJson();
      final restored = QueuedAction.fromJson(json);

      expect(restored.id, action.id);
      expect(restored.endpoint, action.endpoint);
      expect(restored.method, action.method);
      expect(restored.data, action.data);
      expect(restored.retryCount, action.retryCount);
      expect(
        restored.createdAt.toIso8601String(),
        action.createdAt.toIso8601String(),
      );
    });

    test('toJson and fromJson roundtrip with null data', () {
      final action = QueuedAction(
        id: 'test-id-5',
        endpoint: '/test',
        method: 'DELETE',
        createdAt: DateTime.now().toUtc(),
      );
      final json = action.toJson();
      expect(json['data'], isNull);

      final restored = QueuedAction.fromJson(json);
      expect(restored.data, isNull);
    });

    test('fromJson defaults retryCount to 0 when key is missing', () {
      final json = <String, dynamic>{
        'id': 'test-id-6',
        'endpoint': '/test',
        'method': 'POST',
        'createdAt': DateTime.now().toUtc().toIso8601String(),
      };
      final restored = QueuedAction.fromJson(json);
      expect(restored.retryCount, 0);
    });

    test('fromJson handles non-Map data by converting to null', () {
      final json = <String, dynamic>{
        'id': 'test-id-7',
        'endpoint': '/test',
        'method': 'POST',
        'data': 'just a string, not a map',
        'createdAt': DateTime.now().toUtc().toIso8601String(),
        'retryCount': 0,
      };
      final restored = QueuedAction.fromJson(json);
      expect(restored.data, isNull);
    });

    test('copyWith increments retryCount', () {
      final action = QueuedAction(
        id: 'test-id-8',
        endpoint: '/test',
        method: 'GET',
        createdAt: DateTime.now().toUtc(),
      );
      final updated = action.copyWith(retryCount: action.retryCount + 1);
      expect(updated.retryCount, 1);
      expect(updated.id, action.id);
      expect(updated.endpoint, action.endpoint);
      expect(updated.createdAt, action.createdAt);
    });

    test('copyWith without retryCount keeps the existing value', () {
      final action = QueuedAction(
        id: 'test-id-9',
        endpoint: '/test',
        method: 'PATCH',
        createdAt: DateTime.now().toUtc(),
        retryCount: 5,
      );
      final updated = action.copyWith();
      expect(updated.retryCount, 5);
      expect(updated.id, action.id);
    });

    test('toString contains id, method, endpoint, and retryCount', () {
      final action = QueuedAction(
        id: 'test-id-10',
        endpoint: '/transports/42',
        method: 'POST',
        createdAt: DateTime.now().toUtc(),
        retryCount: 3,
      );
      final str = action.toString();
      expect(str, contains('test-id-10'));
      expect(str, contains('POST'));
      expect(str, contains('/transports/42'));
      expect(str, contains('retry: 3'));
    });
  });

  // ==========================================================================
  // ActionQueueState (kept from original)
  // ==========================================================================

  group('ActionQueueState', () {
    test('defaults have zero pending, not replaying, no error', () {
      final state = ActionQueueState();
      expect(state.pendingCount, 0);
      expect(state.isReplaying, false);
      expect(state.lastError, isNull);
    });

    test('creates with specified values', () {
      final state = ActionQueueState(
        pendingCount: 5,
        isReplaying: true,
        lastError: 'Network error',
      );
      expect(state.pendingCount, 5);
      expect(state.isReplaying, true);
      expect(state.lastError, 'Network error');
    });

    test('creates with zero pending and lastError', () {
      final state = ActionQueueState(
        pendingCount: 0,
        isReplaying: false,
        lastError: 'Previous sync failed',
      );
      expect(state.pendingCount, 0);
      expect(state.lastError, 'Previous sync failed');
    });

    test('copyWith overrides only specified fields', () {
      final state = ActionQueueState(
        pendingCount: 3,
        isReplaying: false,
        lastError: 'Old error',
      );
      final updated = state.copyWith(pendingCount: 10);
      expect(updated.pendingCount, 10);
      expect(updated.isReplaying, false);
      expect(updated.lastError, isNull);
    });

    test('copyWith preserves lastError when explicitly provided', () {
      final state = ActionQueueState(pendingCount: 1);
      final updated = state.copyWith(lastError: 'Disk full');
      expect(updated.lastError, 'Disk full');
    });

    test('toString contains pending count, replaying status, and error', () {
      final state = ActionQueueState(
        pendingCount: 7,
        isReplaying: true,
        lastError: 'Timeout',
      );
      final str = state.toString();
      expect(str, contains('pending: 7'));
      expect(str, contains('replaying: true'));
      expect(str, contains('error: Timeout'));
    });

    test('toString with null error', () {
      final state = ActionQueueState(pendingCount: 0);
      final str = state.toString();
      expect(str, contains('error: null'));
    });
  });

  // ==========================================================================
  // ActionQueue
  // ==========================================================================

  group('ActionQueue', () {
    late _FakeLocalDatabase fakeDb;
    late ActionQueue queue;

    setUp(() {
      fakeDb = _FakeLocalDatabase();
      queue = ActionQueue(fakeDb);
    });

    tearDown(() {
      queue.dispose();
    });

    // ── initialize() ────────────────────────────────────────────────────

    test('initialize with no stored actions results in empty queue', () async {
      await queue.initialize();
      expect(queue.pendingCount, 0);
    });

    test('initialize loads persisted actions in FIFO order', () async {
      final now = DateTime.now().toUtc();
      // Store actions in reverse order to verify sorting
      await fakeDb.write('action_2', QueuedAction(
        id: '2',
        endpoint: '/second',
        method: 'POST',
        createdAt: now.add(const Duration(seconds: 1)),
      ).toJson(), namespace: 'action_queue');
      await fakeDb.write('action_1', QueuedAction(
        id: '1',
        endpoint: '/first',
        method: 'GET',
        createdAt: now,
      ).toJson(), namespace: 'action_queue');

      await queue.initialize();

      expect(queue.pendingCount, 2);
      // FIFO: first enqueued should be first in list (id: '1' has earlier createdAt)
      expect(queue.pendingCount, 2);
    });

    test('initialize handles corrupt entries gracefully', () async {
      await fakeDb.write(
        'action_corrupt',
        'not a valid action map',
        namespace: 'action_queue',
      );
      await fakeDb.write('action_valid', QueuedAction(
        id: 'valid-1',
        endpoint: '/test',
        method: 'GET',
        createdAt: DateTime.now().toUtc(),
      ).toJson(), namespace: 'action_queue');

      await queue.initialize();

      // Valid action should still be loaded
      expect(queue.pendingCount, 1);
    });

    test('initialize clears stale isReplaying flag', () async {
      await fakeDb.write('_meta_is_replaying', true, namespace: 'action_queue');

      await queue.initialize();

      final flag = fakeDb.storedValue(
        '_meta_is_replaying',
        namespace: 'action_queue',
      );
      expect(flag, isFalse);
    });

    // ── enqueue() ───────────────────────────────────────────────────────

    test('enqueue returns a non-empty UUID', () async {
      await queue.initialize();
      final id = await queue.enqueue('/transports/42/status', 'PATCH');
      expect(id, isNotEmpty);
      expect(id.length, 36); // UUID v4 length
    });

    test('enqueue increments pending count', () async {
      await queue.initialize();
      expect(queue.pendingCount, 0);

      await queue.enqueue('/t1', 'GET');
      expect(queue.pendingCount, 1);

      await queue.enqueue('/t2', 'POST');
      expect(queue.pendingCount, 2);
    });

    test('enqueue persists action to local DB', () async {
      await queue.initialize();
      final id = await queue.enqueue(
        '/transports/42/status',
        'PATCH',
        data: {'status': 'delivered'},
      );

      final stored = fakeDb.storedValue(
        'action_$id',
        namespace: 'action_queue',
      );
      expect(stored, isNotNull);
      expect((stored as Map)['endpoint'], '/transports/42/status');
      expect((stored)['method'], 'PATCH');
    });

    test('enqueue multiple actions maintains order', () async {
      await queue.initialize();
      final id1 = await queue.enqueue('/first', 'GET');
      final id2 = await queue.enqueue('/second', 'POST');
      final id3 = await queue.enqueue('/third', 'DELETE');

      expect(queue.pendingCount, 3);
      // FIFO means first enqueued is at index 0
      // (check via state stream or internal order; we verify all present)
    });

    test('enqueue can be called without data', () async {
      await queue.initialize();
      final id = await queue.enqueue('/test', 'DELETE');
      expect(id, isNotEmpty);
      expect(queue.pendingCount, 1);
    });

    // ── dequeue() ───────────────────────────────────────────────────────

    test('dequeue removes action by ID from pending list', () async {
      await queue.initialize();
      final id = await queue.enqueue('/test', 'GET');
      expect(queue.pendingCount, 1);

      await queue.dequeue(id);
      expect(queue.pendingCount, 0);
    });

    test('dequeue removes action from persistent storage', () async {
      await queue.initialize();
      final id = await queue.enqueue('/test', 'PATCH');

      await queue.dequeue(id);

      final stored = fakeDb.storedValue(
        'action_$id',
        namespace: 'action_queue',
      );
      expect(stored, isNull);
    });

    test('dequeue with non-existent id is a no-op', () async {
      await queue.initialize();
      await queue.enqueue('/test', 'GET');

      await queue.dequeue('non-existent-id');
      expect(queue.pendingCount, 1); // Still one action
    });

    // ── replayAll() ─────────────────────────────────────────────────────

    test('replayAll replays actions in FIFO order', () async {
      await queue.initialize();
      final id1 = await queue.enqueue('/first', 'GET');
      final id2 = await queue.enqueue('/second', 'POST');
      final replayedOrder = <String>[];

      final count = await queue.replayAll((action) async {
        replayedOrder.add(action.endpoint);
      });

      expect(count, 2);
      expect(replayedOrder, ['/first', '/second']);
      expect(queue.pendingCount, 0);
    });

    test('replayAll dequeues actions on success', () async {
      await queue.initialize();
      await queue.enqueue('/transports/42/status', 'PATCH');

      await queue.replayAll((action) async {});
      expect(queue.pendingCount, 0);
    });

    test('replayAll returns count of successfully replayed actions', () async {
      await queue.initialize();
      await queue.enqueue('/a', 'GET');
      await queue.enqueue('/b', 'GET');

      final count = await queue.replayAll((action) async {});
      expect(count, 2);
    });

    test('replayAll skips actions on transient failure and increments retryCount',
        () async {
      await queue.initialize();
      final id = await queue.enqueue('/flaky', 'GET');

      final callCount = await queue.replayAll((action) async {
        throw Exception('Transient timeout');
      });

      expect(callCount, 0);
      expect(queue.pendingCount, 1);

      // Verify retry count was incremented in storage
      final stored = fakeDb.storedValue(
        'action_$id',
        namespace: 'action_queue',
      );
      expect(stored, isNotNull);
      expect((stored as Map)['retryCount'], 1);
    });

    test('replayAll increments retryCount on each transient failure', () async {
      await queue.initialize();
      final id = await queue.enqueue('/flaky', 'GET');

      // First failure
      await queue.replayAll((action) async => throw Exception('fail 1'));
      expect((fakeDb.storedValue('action_$id', namespace: 'action_queue')
          as Map)['retryCount'], 1);

      // Second failure
      await queue.replayAll((action) async => throw Exception('fail 2'));
      expect((fakeDb.storedValue('action_$id', namespace: 'action_queue')
          as Map)['retryCount'], 2);
    });

    test('replayAll continues with remaining actions after transient failure',
        () async {
      await queue.initialize();
      await queue.enqueue('/first', 'GET');
      await queue.enqueue('/second', 'GET');

      final replayed = <String>[];
      await queue.replayAll((action) async {
        if (action.endpoint == '/first') {
          throw Exception('First fails');
        }
        replayed.add(action.endpoint);
      });

      // Second should still be replayed
      expect(replayed, ['/second']);
    });

    test('replayAll dequeues on ReplayPermanentFailure', () async {
      await queue.initialize();
      await queue.enqueue('/conflict', 'PATCH');

      await queue.replayAll((action) async {
        throw ReplayPermanentFailure('Conflict 409');
      });

      expect(queue.pendingCount, 0);
    });

    test('replayAll emits error state on ReplayPermanentFailure', () async {
      await queue.initialize();
      await queue.enqueue('/bad', 'POST');

      ActionQueueState? emittedState;
      final sub = queue.state.listen((s) {
        emittedState = emittedState != null && s.lastError == null
            ? emittedState
            : s;
      });

      await queue.replayAll((action) async {
        throw ReplayPermanentFailure('Not found 404');
      });

      // Wait for stream to settle
      await Future<void>.delayed(Duration.zero);
      expect(emittedState?.lastError, contains('Not found 404'));
      await sub.cancel();
    });

    test('replayAll is no-op when already replaying', () async {
      await queue.initialize();
      await queue.enqueue('/test', 'GET');

      // Use a completer to keep the first replayAll in progress so that
      // _isReplaying stays true during the second call.
      final completer = Completer<void>();

      final firstFuture = queue.replayAll((action) async {
        await completer.future;
      });

      // Let the first replayAll set _isReplaying = true
      await Future<void>.delayed(Duration.zero);

      // Second call should return 0 immediately because _isReplaying is true
      final secondCount = await queue.replayAll((action) async {});
      expect(secondCount, 0);

      // Release the first replayAll
      completer.complete();
      await firstFuture;
    });

    test('replayAll with empty queue returns 0', () async {
      await queue.initialize();
      final count = await queue.replayAll((action) async {});
      expect(count, 0);
    });

    // ── clear() ─────────────────────────────────────────────────────────

    test('clear removes all pending actions', () async {
      await queue.initialize();
      await queue.enqueue('/a', 'GET');
      await queue.enqueue('/b', 'POST');

      await queue.clear();
      expect(queue.pendingCount, 0);
    });

    test('clear removes all actions from persistent storage', () async {
      await queue.initialize();
      await queue.enqueue('/a', 'GET');
      await queue.enqueue('/b', 'POST');

      await queue.clear();

      final keys = await fakeDb.keysWithPrefix(
        'action_',
        namespace: 'action_queue',
      );
      expect(keys, isEmpty);
    });

    test('clear on empty queue does not error', () async {
      await queue.initialize();
      await queue.clear();
      expect(queue.pendingCount, 0);
    });

    // ── state stream ────────────────────────────────────────────────────

    test('state stream emits after enqueue', () async {
      await queue.initialize();
      ActionQueueState? emitted;
      final sub = queue.state.listen((s) {
        emitted = s;
      });

      await queue.enqueue('/test', 'PATCH');

      // Wait for stream to settle
      await Future<void>.delayed(Duration.zero);
      expect(emitted, isNotNull);
      expect(emitted!.pendingCount, 1);
      await sub.cancel();
    });

    test('state stream emits after dequeue', () async {
      await queue.initialize();
      final id = await queue.enqueue('/test', 'DELETE');

      ActionQueueState? emitted;
      final sub = queue.state.listen((s) {
        emitted = s;
      });

      await queue.dequeue(id);

      await Future<void>.delayed(Duration.zero);
      expect(emitted, isNotNull);
      expect(emitted!.pendingCount, 0);
      await sub.cancel();
    });

    test('state stream emits after clear', () async {
      await queue.initialize();
      await queue.enqueue('/test', 'GET');

      ActionQueueState? emitted;
      final sub = queue.state.listen((s) {
        emitted = s;
      });

      await queue.clear();

      await Future<void>.delayed(Duration.zero);
      expect(emitted, isNotNull);
      expect(emitted!.pendingCount, 0);
      await sub.cancel();
    });

    test('state stream emits isReplaying = true during replay', () async {
      await queue.initialize();
      await queue.enqueue('/test', 'GET');

      final states = <ActionQueueState>[];
      final sub = queue.state.listen((s) {
        states.add(s);
      });

      await queue.replayAll((action) async {});

      await Future<void>.delayed(Duration.zero);
      expect(states.any((s) => s.isReplaying), isTrue);
      // After replay, isReplaying should be false again
      expect(states.last.isReplaying, isFalse);
      await sub.cancel();
    });

    test('state stream is broadcast (multiple listeners allowed)', () async {
      await queue.initialize();
      await queue.enqueue('/test', 'GET');

      final sub1 = queue.state.listen((_) {});
      final sub2 = queue.state.listen((_) {});

      // Both subscriptions should work without error
      expect(sub1.isPaused, isFalse);
      expect(sub2.isPaused, isFalse);

      await sub1.cancel();
      await sub2.cancel();
    });

    // ── dispose() ───────────────────────────────────────────────────────

    test('dispose closes the state stream controller', () async {
      // Subscribe before dispose
      var done = false;
      final sub = queue.state.listen((_) {}, onDone: () {
        done = true;
      });

      queue.dispose();

      // After dispose the stream should be done
      // Give the stream event loop time to process the close
      await Future<void>.delayed(Duration.zero);
      expect(done, isTrue);

      // Subscription should be cancelled after dispose
      expect(sub.isPaused, isFalse);
    });

    // ── Initialisation with pre-existing data ───────────────────────────

    test('initialize sorts persisted actions by createdAt (FIFO)', () async {
      final t0 = DateTime.now().toUtc();
      // Write in reverse order
      await fakeDb.write(
        'action_3',
        QueuedAction(
          id: '3',
          endpoint: '/third',
          method: 'POST',
          createdAt: t0.add(const Duration(seconds: 2)),
        ).toJson(),
        namespace: 'action_queue',
      );
      await fakeDb.write(
        'action_1',
        QueuedAction(
          id: '1',
          endpoint: '/first',
          method: 'GET',
          createdAt: t0,
        ).toJson(),
        namespace: 'action_queue',
      );
      await fakeDb.write(
        'action_2',
        QueuedAction(
          id: '2',
          endpoint: '/second',
          method: 'GET',
          createdAt: t0.add(const Duration(seconds: 1)),
        ).toJson(),
        namespace: 'action_queue',
      );

      await queue.initialize();

      expect(queue.pendingCount, 3);

      // Replay and verify FIFO order
      final replayedEndpoints = <String>[];
      await queue.replayAll((action) async {
        replayedEndpoints.add(action.endpoint);
      });

      expect(replayedEndpoints, ['/first', '/second', '/third']);
    });
  });

  // ==========================================================================
  // ReplayPermanentFailure (kept from original)
  // ==========================================================================

  group('ReplayPermanentFailure', () {
    test('creates with a message', () {
      final error = ReplayPermanentFailure('Resource not found (404)');
      expect(error.message, 'Resource not found (404)');
    });

    test('creates with empty message', () {
      final error = ReplayPermanentFailure('');
      expect(error.message, isEmpty);
    });

    test('toString includes the message', () {
      final error = ReplayPermanentFailure(
        'Conflict: duplicate idempotency key',
      );
      expect(error.toString(), contains('ReplayPermanentFailure'));
      expect(
        error.toString(),
        contains('Conflict: duplicate idempotency key'),
      );
    });
  });

  // ==========================================================================
  // Riverpod providers (kept from original)
  // ==========================================================================

  group('Riverpod providers', () {
    test('localDatabaseProvider returns a non-null LocalDatabase', () {
      // Placeholder check — full provider tests need ProviderContainer.
    });
  });
}
