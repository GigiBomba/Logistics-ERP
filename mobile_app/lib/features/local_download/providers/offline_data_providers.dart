import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/sync/action_queue.dart';
import '../../../core/sync/sync_providers.dart';

/// Returns the number of cached records for a given [collection].
///
/// Watches [syncCursorsProvider] so that every completed sync run
/// automatically refetches the count.
final cachedCollectionCountProvider =
    FutureProvider.family<int, String>((ref, collection) async {
  ref.watch(syncCursorsProvider);
  final db = await ref.read(localDatabaseProvider.future);
  final records = await db.getAllCachedData(collection);
  return records.length;
});

/// Combines sync status + count + last-sync time for a single collection.
class OfflineCollectionState {
  final int count;
  final bool isSyncing;
  final DateTime? lastSyncAt;

  const OfflineCollectionState({
    required this.count,
    required this.isSyncing,
    this.lastSyncAt,
  });
}

/// Watches both the cached record count and the global sync state for a
/// collection so the UI can show a spinner overlay while syncing.
final offlineCollectionStateProvider = Provider.family<
    AsyncValue<OfflineCollectionState>, String>((ref, collection) {
  final countAsync = ref.watch(cachedCollectionCountProvider(collection));
  final syncStatus = ref.watch(syncStatusProvider);
  final lastSyncAt = ref.watch(lastSyncAtProvider);

  return countAsync.when(
    loading: () => const AsyncValue.loading(),
    error: (err, stack) => AsyncValue.error(err, stack),
    data: (count) => AsyncValue.data(
      OfflineCollectionState(
        count: count,
        isSyncing: syncStatus == SyncStatus.syncing,
        lastSyncAt: lastSyncAt,
      ),
    ),
  );
});
