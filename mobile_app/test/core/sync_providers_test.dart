import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/core/sync/delta_sync_service.dart';
import 'package:operion_mobile/core/sync/sync_providers.dart';

// =============================================================================
// Fake DeltaSyncService used to exercise the SyncCoordinator in isolation.
// =============================================================================

class _FakeDeltaSyncService implements DeltaSyncService {
  /// Entities that `sync` was called for, in order.
  final List<String> syncedEntities = [];

  /// Per-entity record counts returned by successful syncs.
  Map<String, int> recordsByEntity = {};

  /// Per-entity cursors returned by [getLastCursor].
  Map<String, String> cursorsByEntity = {};

  /// If set, `sync` for this entity returns a failure (and the coordinator
  /// stops there).
  String? failEntity;

  @override
  Future<SyncResult> sync({required String entityType}) async {
    syncedEntities.add(entityType);
    if (failEntity == entityType) {
      return SyncResult(
        success: false,
        recordsSynced: 0,
        error: 'boom $entityType',
      );
    }
    return SyncResult(
      success: true,
      recordsSynced: recordsByEntity[entityType] ?? 0,
    );
  }

  @override
  Future<SyncResult> fullSync({required String entityType}) async {
    return SyncResult(success: true, recordsSynced: 0);
  }

  @override
  Future<String?> getLastCursor(String entityType) async =>
      cursorsByEntity[entityType];

  @override
  Future<void> updateCursor(String entityType, String cursor) async {
    cursorsByEntity[entityType] = cursor;
  }
}

void main() {
  // ==========================================================================
  // SyncStatus enum
  // ==========================================================================

  group('SyncStatus', () {
    test('has idle value', () {
      expect(SyncStatus.idle, isA<SyncStatus>());
    });

    test('has syncing value', () {
      expect(SyncStatus.syncing, isA<SyncStatus>());
    });

    test('has error value', () {
      expect(SyncStatus.error, isA<SyncStatus>());
    });

    test('has success value', () {
      expect(SyncStatus.success, isA<SyncStatus>());
    });

    test('contains all four expected values', () {
      expect(SyncStatus.values, hasLength(4));
      expect(SyncStatus.values, containsAll([
        SyncStatus.idle,
        SyncStatus.syncing,
        SyncStatus.error,
        SyncStatus.success,
      ]));
    });

    test('idle is the first value (default)', () {
      expect(SyncStatus.values.first, SyncStatus.idle);
    });
  });

  // ==========================================================================
  // syncTriggerProvider
  // ==========================================================================

  group('syncTriggerProvider', () {
    test('initial state is null', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      final value = container.read(syncTriggerProvider);
      expect(value, isNull);
    });

    test('can be set to a DateTime to trigger sync', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      final now = DateTime.now();
      container.read(syncTriggerProvider.notifier).state = now;

      final value = container.read(syncTriggerProvider);
      expect(value, now);
    });

    test('can be reset to null', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      container.read(syncTriggerProvider.notifier).state = DateTime.now();
      container.read(syncTriggerProvider.notifier).state = null;

      expect(container.read(syncTriggerProvider), isNull);
    });

    test('can be updated multiple times', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      final t1 = DateTime(2025, 1, 1);
      final t2 = DateTime(2025, 6, 15);

      container.read(syncTriggerProvider.notifier).state = t1;
      expect(container.read(syncTriggerProvider), t1);

      container.read(syncTriggerProvider.notifier).state = t2;
      expect(container.read(syncTriggerProvider), t2);
    });
  });

  // ==========================================================================
  // syncStatusProvider
  // ==========================================================================

  group('syncStatusProvider', () {
    test('initial state is idle', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      expect(container.read(syncStatusProvider), SyncStatus.idle);
    });

    test('can be updated to syncing', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      container.read(syncStatusProvider.notifier).state = SyncStatus.syncing;
      expect(container.read(syncStatusProvider), SyncStatus.syncing);
    });

    test('can be updated to success', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      container.read(syncStatusProvider.notifier).state = SyncStatus.success;
      expect(container.read(syncStatusProvider), SyncStatus.success);
    });

    test('can be updated to error', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      container.read(syncStatusProvider.notifier).state = SyncStatus.error;
      expect(container.read(syncStatusProvider), SyncStatus.error);
    });

    test('can transition through multiple states', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      final notifier = container.read(syncStatusProvider.notifier);

      expect(container.read(syncStatusProvider), SyncStatus.idle);

      notifier.state = SyncStatus.syncing;
      expect(container.read(syncStatusProvider), SyncStatus.syncing);

      notifier.state = SyncStatus.success;
      expect(container.read(syncStatusProvider), SyncStatus.success);

      // Back to idle
      notifier.state = SyncStatus.idle;
      expect(container.read(syncStatusProvider), SyncStatus.idle);
    });
  });

  // ==========================================================================
  // syncErrorMessageProvider
  // ==========================================================================

  group('syncErrorMessageProvider', () {
    test('initial state is null', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      expect(container.read(syncErrorMessageProvider), isNull);
    });

    test('can be set to an error message', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      container.read(syncErrorMessageProvider.notifier).state =
          'Connection timeout';
      expect(container.read(syncErrorMessageProvider), 'Connection timeout');
    });

    test('can be cleared back to null', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      container.read(syncErrorMessageProvider.notifier).state = 'Error';
      container.read(syncErrorMessageProvider.notifier).state = null;

      expect(container.read(syncErrorMessageProvider), isNull);
    });

    test('can be updated with empty string', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      container.read(syncErrorMessageProvider.notifier).state = '';
      expect(container.read(syncErrorMessageProvider), isEmpty);
    });
  });

  // ==========================================================================
  // syncRecordsCountProvider
  // ==========================================================================

  group('syncRecordsCountProvider', () {
    test('initial state is 0', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      expect(container.read(syncRecordsCountProvider), 0);
    });

    test('can be updated to a positive count', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      container.read(syncRecordsCountProvider.notifier).state = 42;
      expect(container.read(syncRecordsCountProvider), 42);
    });

    test('can be reset to zero', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      container.read(syncRecordsCountProvider.notifier).state = 100;
      container.read(syncRecordsCountProvider.notifier).state = 0;

      expect(container.read(syncRecordsCountProvider), 0);
    });

    test('can handle large record counts', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      container.read(syncRecordsCountProvider.notifier).state = 999999;
      expect(container.read(syncRecordsCountProvider), 999999);
    });
  });

  // ==========================================================================
  // syncCursorsProvider
  // ==========================================================================

  group('syncCursorsProvider', () {
    test('initial state is empty map', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      expect(container.read(syncCursorsProvider), {});
    });

    test('can be updated with a cursor map', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      container.read(syncCursorsProvider.notifier).state = {
        'transport': 'cursor-1',
        'message': 'cursor-2',
      };

      final cursors = container.read(syncCursorsProvider);
      expect(cursors, hasLength(2));
      expect(cursors['transport'], 'cursor-1');
      expect(cursors['message'], 'cursor-2');
    });

    test('can be cleared', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      container.read(syncCursorsProvider.notifier).state = {
        'transport': 'abc',
      };
      container.read(syncCursorsProvider.notifier).state = {};

      expect(container.read(syncCursorsProvider), isEmpty);
    });

    test('can be updated incrementally', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      final notifier = container.read(syncCursorsProvider.notifier);

      notifier.state = {'transport': 't-1'};
      expect(container.read(syncCursorsProvider), {'transport': 't-1'});

      notifier.state = {'transport': 't-2', 'message': 'm-1'};
      final cursors = container.read(syncCursorsProvider);
      expect(cursors['transport'], 't-2');
      expect(cursors['message'], 'm-1');
    });
  });

  // ==========================================================================
  // Cross-provider interaction
  // ==========================================================================

  group('cross-provider interaction', () {
    test('providers are independent', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      // Update all providers
      container.read(syncStatusProvider.notifier).state = SyncStatus.syncing;
      container.read(syncErrorMessageProvider.notifier).state = 'Loading...';
      container.read(syncRecordsCountProvider.notifier).state = 5;
      container.read(syncCursorsProvider.notifier).state = {'x': 'y'};

      // Each should reflect its own state
      expect(container.read(syncStatusProvider), SyncStatus.syncing);
      expect(container.read(syncErrorMessageProvider), 'Loading...');
      expect(container.read(syncRecordsCountProvider), 5);
      expect(container.read(syncCursorsProvider), {'x': 'y'});

      // Cursors provider should not affect others
      container.read(syncCursorsProvider.notifier).state = {};
      expect(container.read(syncStatusProvider), SyncStatus.syncing);
      expect(container.read(syncErrorMessageProvider), 'Loading...');
    });

    test('full sync lifecycle state transitions', () {
      final container = ProviderContainer();
      addTearDown(() => container.dispose());

      final status = container.read(syncStatusProvider.notifier);
      final error = container.read(syncErrorMessageProvider.notifier);
      final count = container.read(syncRecordsCountProvider.notifier);

      // Initial state
      expect(container.read(syncStatusProvider), SyncStatus.idle);
      expect(container.read(syncErrorMessageProvider), isNull);
      expect(container.read(syncRecordsCountProvider), 0);

      // Start sync
      status.state = SyncStatus.syncing;
      expect(container.read(syncStatusProvider), SyncStatus.syncing);

      // Sync completes successfully
      status.state = SyncStatus.success;
      count.state = 15;
      expect(container.read(syncStatusProvider), SyncStatus.success);
      expect(container.read(syncRecordsCountProvider), 15);

      // Another sync with error
      status.state = SyncStatus.syncing;
      status.state = SyncStatus.error;
      error.state = 'Server returned 500';
      expect(container.read(syncStatusProvider), SyncStatus.error);
      expect(container.read(syncErrorMessageProvider), 'Server returned 500');

      // Reset for next sync
      status.state = SyncStatus.idle;
      error.state = null;
      count.state = 0;
      expect(container.read(syncStatusProvider), SyncStatus.idle);
      expect(container.read(syncErrorMessageProvider), isNull);
      expect(container.read(syncRecordsCountProvider), 0);
    });
  });

  // ==========================================================================
  // SyncCoordinator
  // ==========================================================================

  group('SyncCoordinator', () {
    ProviderContainer buildContainer(_FakeDeltaSyncService fake) {
      final container = ProviderContainer(overrides: [
        deltaSyncServiceProvider.overrideWith((ref) => fake),
      ]);
      addTearDown(() => container.dispose());
      return container;
    }

    test('writing trigger runs coordinator through all 4 entities', () async {
      final fake = _FakeDeltaSyncService()
        ..recordsByEntity = {
          'transport': 2,
          'message': 3,
          'drivers': 1,
          'fleet': 4,
        }
        ..cursorsByEntity = {
          'transport': 't-cur',
          'message': 'm-cur',
          'drivers': 'd-cur',
          'fleet': 'f-cur',
        };
      final container = buildContainer(fake);

      // Reading the provider activates the trigger listener.
      final coordinator = container.read(syncCoordinatorProvider);
      container.read(syncTriggerProvider.notifier).state = DateTime.now();
      await coordinator.activeRun;

      expect(fake.syncedEntities, ['transport', 'message', 'drivers', 'fleet']);
      expect(container.read(syncStatusProvider), SyncStatus.success);
      expect(container.read(syncRecordsCountProvider), 10);
      expect(container.read(syncCursorsProvider), {
        'transport': 't-cur',
        'message': 'm-cur',
        'drivers': 'd-cur',
        'fleet': 'f-cur',
      });
    });

    test('status transitions idle -> syncing -> success', () async {
      final fake = _FakeDeltaSyncService();
      final container = buildContainer(fake);

      final transitions = <SyncStatus>[];
      container.listen<SyncStatus>(
        syncStatusProvider,
        (previous, next) => transitions.add(next),
      );

      final coordinator = container.read(syncCoordinatorProvider);
      container.read(syncTriggerProvider.notifier).state = DateTime.now();
      await coordinator.activeRun;

      // idle is the default; the listener observes syncing then success.
      expect(transitions, [SyncStatus.syncing, SyncStatus.success]);
    });

    test('error path sets error message and error status', () async {
      final fake = _FakeDeltaSyncService()..failEntity = 'message';
      final container = buildContainer(fake);

      final coordinator = container.read(syncCoordinatorProvider);
      container.read(syncTriggerProvider.notifier).state = DateTime.now();
      await coordinator.activeRun;

      expect(container.read(syncStatusProvider), SyncStatus.error);
      expect(container.read(syncErrorMessageProvider), 'boom message');
      // Sync stopped at the failing entity.
      expect(fake.syncedEntities, ['transport', 'message']);
    });

    test('records count accumulates across entities', () async {
      final fake = _FakeDeltaSyncService()
        ..recordsByEntity = {
          'transport': 5,
          'message': 7,
          'drivers': 0,
          'fleet': 3,
        };
      final container = buildContainer(fake);

      final coordinator = container.read(syncCoordinatorProvider);
      container.read(syncTriggerProvider.notifier).state = DateTime.now();
      await coordinator.activeRun;

      expect(container.read(syncRecordsCountProvider), 15);
    });
  });
}
