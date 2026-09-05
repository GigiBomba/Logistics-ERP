import 'dart:developer' as developer;

import '../storage/local_db.dart';
import '../network/endpoints/sync_endpoints.dart';

// ── Data models ───────────────────────────────────────────────────────

/// Outcome of a single delta-sync cycle.
class SyncResult {
  /// Whether the sync completed without errors.
  final bool success;

  /// Number of records that were synced.
  final int recordsSynced;

  /// Error message if [success] is `false`.
  final String? error;

  /// When the sync finished.
  final DateTime timestamp;

  SyncResult({
    required this.success,
    required this.recordsSynced,
    this.error,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();

  @override
  String toString() =>
      'SyncResult(success: $success, records: $recordsSynced, error: $error)';
}

// ── Delta sync service ────────────────────────────────────────────────

/// Performs delta (incremental) synchronisation with the backend.
///
/// For a given [entityType] (e.g. `transport`, `message`) the service:
/// 1. Reads the last-known sync cursor from [LocalDatabase].
/// 2. Fetches changed records page by page, echoing the server cursor.
/// 3. Persists the new cursor returned by the server.
///
/// ## Cursor contract
///
/// The backend cursor is OPAQUE — a compound `"<ts>|<id>"` string for
/// timestamp entities, a numeric string for fleet. The client stores and
/// echoes it verbatim; it is never split, parsed, or reformatted. A `null`
/// cursor means "no cursor": the next sync starts from the first page and no
/// `since` parameter is sent.
///
/// Pages are fetched until the backend reports `has_more == false`, bounded
/// by [maxPagesPerRun] so a misbehaving backend can never cause an infinite
/// loop.
class DeltaSyncService {
  final SyncEndpoints _endpoints;
  final LocalDatabase _db;

  /// Namespace used inside [LocalDatabase] for sync cursors.
  static const String _cursorNamespace = 'sync_cursors';

  /// Hard cap on the number of pages fetched per sync run. Guards against a
  /// backend that keeps returning `has_more: true` forever.
  static const int maxPagesPerRun = 50;

  DeltaSyncService(this._endpoints, this._db);

  // ── Public API ─────────────────────────────────────────────────────

  /// Performs a delta sync for [entityType].
  ///
  /// Starts from the stored cursor (if any) and paginates until the backend
  /// reports `has_more == false`. Returns a [SyncResult] describing the
  /// outcome.
  Future<SyncResult> sync({required String entityType}) async {
    final cursor = await getLastCursor(entityType);
    return _runSyncLoop(
      entityType: entityType,
      startCursor: cursor,
      persistCursor: true,
    );
  }

  /// Performs a full (bulk) sync for [entityType], ignoring any existing
  /// cursor.
  ///
  /// Starts from the first page (no `since`) and paginates until done. The
  /// stored cursor is only overwritten if the whole loop completes.
  Future<SyncResult> fullSync({required String entityType}) async {
    return _runSyncLoop(
      entityType: entityType,
      startCursor: null,
      persistCursor: true,
    );
  }

  // ── Shared paginated loop ───────────────────────────────────────────

  /// Fetches all pages for [entityType] and merges them into the local store.
  ///
  /// - Page 1 never sends `since` unless [startCursor] is non-null; every
  ///   subsequent page sends the cursor from the previous response verbatim.
  /// - Each page is written with a single [LocalDatabase.cacheMany] call.
  /// - The loop stops when `has_more == false` or when [maxPagesPerRun]
  ///   pages have been fetched (in which case it fails instead of spinning).
  /// - The final non-null cursor is persisted only when [persistCursor] is
  ///   set and the loop completed without error.
  Future<SyncResult> _runSyncLoop({
    required String entityType,
    required String? startCursor,
    required bool persistCursor,
  }) async {
    var cursor = startCursor;
    var totalRecords = 0;
    var pages = 0;
    var hasMore = true;
    String? lastCursor;

    try {
      while (hasMore) {
        if (pages >= maxPagesPerRun) {
          // Cap-hit: cached data is always at-or-before the cursor returned by
          // the last fetched page, so advancing the stored cursor here is safe
          // and lets the next run resume from where this one stopped instead of
          // refetching the same pages forever.
          if (lastCursor != null) {
            await updateCursor(entityType, lastCursor);
          }
          final error = 'Sync for $entityType exceeded the maximum of '
              '$maxPagesPerRun pages; giving up';
          developer.log('DeltaSync: $error', name: 'DeltaSync');
          return SyncResult(
            success: false,
            recordsSynced: totalRecords,
            error: error,
          );
        }

        final response = await _endpoints.syncEntity(
          entityType,
          cursor: cursor,
        );

        final body = response.data;
        if (body is! Map<String, dynamic>) {
          return SyncResult(
            success: false,
            recordsSynced: totalRecords,
            error: 'Unexpected response format for $entityType sync',
          );
        }

        final records = body['records'];
        if (records is! List) {
          return SyncResult(
            success: false,
            recordsSynced: totalRecords,
            error:
                'Malformed sync response for $entityType: missing "records" list',
          );
        }

        // Merge this page's records into a single batch write.
        final pageMap = <String, Map<String, dynamic>>{};
        for (final record in records) {
          if (record is Map<String, dynamic>) {
            final recordId = (record['id'] ?? record['_id']).toString();
            pageMap[recordId] = record;
          }
        }
        if (pageMap.isNotEmpty) {
          await _db.cacheMany(entityType, pageMap);
          totalRecords += pageMap.length;
        }

        final rawCursor = body['cursor'];
        lastCursor = rawCursor is String ? rawCursor : null;
        hasMore = body['has_more'] == true;
        pages++;

        developer.log(
          'DeltaSync: $entityType page $pages fetched ${pageMap.length} '
          'record(s) (total $totalRecords, has_more: $hasMore, '
          'cursor: ${lastCursor != null ? _shortCursor(lastCursor) : 'none'})',
          name: 'DeltaSync',
        );

        // The next page continues from the cursor this response returned.
        cursor = lastCursor;
      }

      // Persist the final cursor only when the run completed cleanly, and
      // never persist a null cursor.
      if (persistCursor && lastCursor != null) {
        await updateCursor(entityType, lastCursor);
      }

      return SyncResult(success: true, recordsSynced: totalRecords);
    } catch (e) {
      developer.log(
        'DeltaSync loop($entityType): $e',
        name: 'DeltaSync',
      );
      return SyncResult(
        success: false,
        recordsSynced: totalRecords,
        error: e.toString(),
      );
    }
  }

  static String _shortCursor(String cursor) =>
      cursor.length > 8 ? '${cursor.substring(0, 8)}…' : cursor;

  // ── Cursor persistence ────────────────────────────────────────────────

  /// Retrieves the last-known sync cursor for [entityType].
  ///
  /// Returns `null` when no prior sync has been performed.
  Future<String?> getLastCursor(String entityType) async {
    try {
      final raw = await _db.read(entityType, namespace: _cursorNamespace);
      return raw as String?;
    } catch (e) {
      developer.log(
        'DeltaSync.getLastCursor($entityType): $e',
        name: 'DeltaSync',
      );
      return null;
    }
  }

  /// Persists the [cursor] returned by the server for [entityType].
  ///
  /// The cursor is stored verbatim. Callers must only pass a non-null value —
  /// a null cursor is never persisted.
  Future<void> updateCursor(String entityType, String cursor) async {
    try {
      await _db.write(entityType, cursor, namespace: _cursorNamespace);
    } catch (e) {
      developer.log(
        'DeltaSync.updateCursor($entityType): $e',
        name: 'DeltaSync',
      );
      rethrow;
    }
  }
}