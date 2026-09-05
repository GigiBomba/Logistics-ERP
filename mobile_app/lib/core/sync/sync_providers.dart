import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_providers.dart';
import '../network/endpoints/sync_endpoints.dart';
import '../sync/action_queue.dart';
import 'delta_sync_service.dart';

// ── Sync status ───────────────────────────────────────────────────────

/// Describes the current state of a sync cycle.
enum SyncStatus {
  /// No sync is in progress and the last sync was successful (or never run).
  idle,

  /// A sync is currently running.
  syncing,

  /// The last sync completed with errors.
  error,

  /// The last sync completed successfully.
  success,
}

// ── Providers ─────────────────────────────────────────────────────────

/// Writing a non-null [DateTime] to this provider triggers a sync for the
/// known entities. The [SyncCoordinator] watches this provider and runs the
/// sync engine when a timestamp is written.
///
/// Usage:
/// ```dart
/// ref.read(syncTriggerProvider.notifier).state = DateTime.now();
/// ```
final syncTriggerProvider = StateProvider<DateTime?>((ref) => null);

/// Global sync status used by the UI to show spinners / banners.
final syncStatusProvider = StateProvider<SyncStatus>((ref) => SyncStatus.idle);

/// The last error message from a failed sync, if any.
final syncErrorMessageProvider = StateProvider<String?>((ref) => null);

/// The number of records synced during the last successful (or partially
/// successful) sync cycle.
final syncRecordsCountProvider = StateProvider<int>((ref) => 0);

/// Writable provider for the sync cursor map.
///
/// Maps entity type (e.g. `'transport'`, `'message'`) to the last-known
/// cursor string. Driving this from a provider makes it easy to reactively
/// rebuild widgets that depend on sync state.
final syncCursorsProvider =
    StateProvider<Map<String, String>>((ref) => const {});

// ── Sync engine wiring ────────────────────────────────────────────────

/// Provides the [DeltaSyncService] backing the [SyncCoordinator].
///
/// Built lazily from the shared [ApiClient] and the initialised shared
/// [LocalDatabase]. Override in tests with a fake service.
final deltaSyncServiceProvider = FutureProvider<DeltaSyncService>((ref) async {
  final apiClient = ref.watch(apiClientProvider);
  final db = await ref.watch(localDatabaseProvider.future);
  return DeltaSyncService(SyncEndpoints(apiClient), db);
});

/// Coordinates a full sync cycle across every synced entity.
///
/// Watches [syncTriggerProvider]: whenever a timestamp is written, a run
/// starts that syncs each entity sequentially (concurrency 1) and publishes
/// progress through [syncStatusProvider], [syncErrorMessageProvider],
/// [syncRecordsCountProvider] and [syncCursorsProvider].
class SyncCoordinator {
  /// Entities synced on every trigger, in order.
  static const List<String> syncedEntities = [
    'transport',
    'message',
    'drivers',
    'fleet',
  ];

  final Ref _ref;

  /// The run currently in flight, if any. Coalesces concurrent triggers so
  /// only one run executes at a time.
  Future<void>? _activeRun;

  SyncCoordinator(this._ref) {
    _ref.listen<DateTime?>(syncTriggerProvider, (previous, next) {
      if (next != null) {
        _activeRun = runNow();
      }
    });
  }

  /// The in-flight (or just-triggered) run, when one is active. Awaitable in
  /// tests and by Phase-3 trigger wiring that wants to know when sync ends.
  Future<void>? get activeRun => _activeRun;

  /// Runs a delta sync for every [syncedEntities] entity, sequentially.
  ///
  /// If a run is already in flight, this returns the existing run instead of
  /// starting a second one.
  Future<void> runNow() {
    final existing = _activeRun;
    if (existing != null) return existing;

    final run = _doRun();
    _activeRun = run;
    run.whenComplete(() {
      if (identical(_activeRun, run)) _activeRun = null;
    });
    return run;
  }

  Future<void> _doRun() async {
    try {
      final service = await _ref.read(deltaSyncServiceProvider.future);

      _ref.read(syncStatusProvider.notifier).state = SyncStatus.syncing;
      _ref.read(syncErrorMessageProvider.notifier).state = null;

      var totalRecords = 0;
      final cursors = <String, String>{};
      var failed = false;

      for (final entity in syncedEntities) {
        final result = await service.sync(entityType: entity);
        totalRecords += result.recordsSynced;

        final cursor = await service.getLastCursor(entity);
        if (cursor != null) cursors[entity] = cursor;

        if (!result.success) {
          failed = true;
          _ref.read(syncErrorMessageProvider.notifier).state =
              result.error ?? 'Sync failed for $entity';
          break;
        }
      }

      _ref.read(syncRecordsCountProvider.notifier).state = totalRecords;
      _ref.read(syncCursorsProvider.notifier).state = cursors;
      _ref.read(syncStatusProvider.notifier).state =
          failed ? SyncStatus.error : SyncStatus.success;
    } catch (e) {
      _ref.read(syncErrorMessageProvider.notifier).state = e.toString();
      _ref.read(syncStatusProvider.notifier).state = SyncStatus.error;
    }
  }
}

/// Provides the [SyncCoordinator] that reacts to [syncTriggerProvider].
///
/// Phase-3 trigger wiring consumes this provider — reading it (or listening
/// to it from a widget) activates the trigger listener.
final syncCoordinatorProvider = Provider<SyncCoordinator>((ref) {
  return SyncCoordinator(ref);
});