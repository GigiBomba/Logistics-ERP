import 'package:flutter_riverpod/flutter_riverpod.dart';

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

/// Writing a non-null [DateTime] to this provider triggers a sync for a
/// specific entity type (the caller is responsible for listening and acting).
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
