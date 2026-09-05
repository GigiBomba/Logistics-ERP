import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/sync_endpoints.dart';
import 'package:operion_mobile/core/storage/local_db.dart';
import 'package:operion_mobile/core/sync/delta_sync_service.dart';

// =============================================================================
// Fakes
// =============================================================================

/// Fake endpoint layer matching the real mobile sync contract:
/// `{"records": [...], "cursor": <opaque string|null>, "has_more": bool}`.
///
/// Supports returning a sequence of pages and recording every `since` cursor
/// that was sent (opaque, verbatim — including null).
class _FakeSyncEndpoints implements SyncEndpoints {
  @override
  ApiClient get client => throw UnimplementedError('client not used in tests');

  final List<Response> _queue = [];
  Exception? _error;
  bool _infiniteHasMore = false;

  /// Every `since` cursor sent, in order. `null` means "no cursor".
  final List<String?> cursorCalls = [];

  /// Every entity type requested, in order.
  final List<String> entityCalls = [];

  int syncEntityCallCount = 0;

  void returnsSyncEntityPages(List<Response> pages) {
    _queue
      ..clear()
      ..addAll(pages);
    _error = null;
    _infiniteHasMore = false;
  }

  void returnsSyncEntity(Response response) => returnsSyncEntityPages([response]);

  void throwsOnSyncEntity(Exception e) {
    _error = e;
    _queue.clear();
    _infiniteHasMore = false;
  }

  /// Makes every syncEntity call return a `has_more: true` page, so a sync run
  /// can only terminate via the page cap.
  void returnsInfiniteHasMore() {
    _queue.clear();
    _error = null;
    _infiniteHasMore = true;
  }

  @override
  Future<Response> syncEntity(String entityType, {String? cursor}) async {
    syncEntityCallCount++;
    entityCalls.add(entityType);
    cursorCalls.add(cursor);
    if (_error != null) throw _error!;
    if (_queue.isNotEmpty) return _queue.removeAt(0);
    if (_infiniteHasMore) {
      return Response(
        data: {
          'records': <Map<String, dynamic>>[{'id': 'x'}],
          'cursor': 'cursor-x',
          'has_more': true,
        },
        requestOptions: RequestOptions(path: ''),
      );
    }
    return Response(
      data: {
        'records': <Map<String, dynamic>>[],
        'cursor': null,
        'has_more': false,
      },
      requestOptions: RequestOptions(path: ''),
    );
  }

  void reset() {
    _queue.clear();
    _error = null;
    _infiniteHasMore = false;
    cursorCalls.clear();
    entityCalls.clear();
    syncEntityCallCount = 0;
  }
}

class _FakeLocalDatabase implements LocalDatabase {
  final _data = <String, Map<String, dynamic>>{};
  final List<Map<String, dynamic>> cacheDataCalls = [];

  /// One entry per [cacheMany] call, recording the batch map passed in.
  final List<Map<String, Map<String, dynamic>>> cacheManyCalls = [];

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
    _data.putIfAbsent(namespace, () => <String, dynamic>{});
    _data[namespace]![key] = value;
  }

  @override
  Future<void> delete(String key, {String namespace = 'default'}) async {
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
        .toList();
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
    cacheDataCalls.add({'collection': collection, 'key': key, 'data': data});
    _data.putIfAbsent(collection, () => <String, dynamic>{});
    _data[collection]![key] = Map<String, dynamic>.from(data);
  }

  @override
  Future<void> cacheMany(
    String collection,
    Map<String, Map<String, dynamic>> records,
  ) async {
    cacheManyCalls.add(records);
    for (final entry in records.entries) {
      await cacheData(collection, entry.key, entry.value);
    }
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
  Future<List<Map<String, dynamic>>> getAllCachedData(String collection) async {
    final col = _data[collection];
    if (col == null) return [];
    return col.values
        .whereType<Map<String, dynamic>>()
        .map((m) => Map<String, dynamic>.from(m))
        .toList();
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

  /// Test helper: returns stored cursor for [entityType], or null.
  String? getStoredCursor(String entityType) {
    final ns = _data['sync_cursors'];
    return ns?[entityType] as String?;
  }
}

// =============================================================================
// SyncResult tests (kept from original)
// =============================================================================

void main() {
  group('SyncResult', () {
    test('creates with success state', () {
      final result = SyncResult(success: true, recordsSynced: 42);
      expect(result.success, isTrue);
      expect(result.recordsSynced, 42);
      expect(result.error, isNull);
      expect(result.timestamp, isNotNull);
    });

    test('creates with error state', () {
      final result = SyncResult(
        success: false,
        recordsSynced: 0,
        error: 'Connection timeout',
      );
      expect(result.success, isFalse);
      expect(result.recordsSynced, 0);
      expect(result.error, 'Connection timeout');
    });

    test('creates with zero records synced on success', () {
      final result = SyncResult(success: true, recordsSynced: 0);
      expect(result.success, isTrue);
      expect(result.recordsSynced, 0);
      expect(result.error, isNull);
    });

    test('creates with empty string error', () {
      final result = SyncResult(
        success: false,
        recordsSynced: 0,
        error: '',
      );
      expect(result.error, isEmpty);
    });

    test('timestamp defaults to current time when not provided', () {
      final before = DateTime.now();
      final result = SyncResult(success: true, recordsSynced: 10);
      final after = DateTime.now();

      expect(
        result.timestamp.isAfter(before) || result.timestamp == before,
        isTrue,
      );
      expect(
        result.timestamp.isBefore(after) || result.timestamp == after,
        isTrue,
      );
    });

    test('timestamp can be provided explicitly', () {
      final customTime = DateTime(2025, 1, 15, 10, 30, 0);
      final result = SyncResult(
        success: true,
        recordsSynced: 100,
        timestamp: customTime,
      );
      expect(result.timestamp, customTime);
    });

    test('timestamp is not altered by the constructor when provided', () {
      final fixedTime = DateTime(2024, 12, 31, 23, 59, 59);
      final result = SyncResult(
        success: false,
        recordsSynced: 0,
        error: 'Server unreachable',
        timestamp: fixedTime,
      );
      expect(result.timestamp, fixedTime);
    });

    test('toString contains success, recordsSynced, and error', () {
      final result = SyncResult(
        success: false,
        recordsSynced: 3,
        error: 'Not found',
      );
      final str = result.toString();
      expect(str, contains('success: false'));
      expect(str, contains('records: 3'));
      expect(str, contains('Not found'));
    });

    test('toString with null error shows "null"', () {
      final result = SyncResult(success: true, recordsSynced: 100);
      final str = result.toString();
      expect(str, contains('success: true'));
      expect(str, contains('records: 100'));
      expect(str, contains('error: null'));
    });

    test('toString with max int recordsSynced boundary', () {
      final result = SyncResult(
        success: true,
        recordsSynced: 9223372036854775807,
      );
      final str = result.toString();
      expect(str, contains('records: 9223372036854775807'));
    });
  });

  // ==========================================================================
  // DeltaSyncService tests
  // ==========================================================================

  group('DeltaSyncService', () {
    late _FakeSyncEndpoints fakeEndpoints;
    late _FakeLocalDatabase fakeDb;
    late DeltaSyncService service;

    setUp(() {
      fakeEndpoints = _FakeSyncEndpoints();
      fakeDb = _FakeLocalDatabase();
      service = DeltaSyncService(fakeEndpoints, fakeDb);
    });

    tearDown(() {
      fakeEndpoints.reset();
    });

    // ── Initial sync (no prior cursor) ──────────────────────────────────

    test('initial sync calls syncEntity with null cursor', () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': '1', 'name': 'Alpha'}],
            'cursor': 'cursor-001',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      final result = await service.sync(entityType: 'transport');

      expect(fakeEndpoints.syncEntityCallCount, 1);
      expect(fakeEndpoints.entityCalls, ['transport']);
      expect(fakeEndpoints.cursorCalls, [null]);
      expect(result.success, isTrue);
      expect(result.recordsSynced, 1);
    });

    test('initial sync writes cursor to local DB', () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': '1'}],
            'cursor': 'cursor-abc-123',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      await service.sync(entityType: 'transport');

      expect(fakeDb.getStoredCursor('transport'), 'cursor-abc-123');
    });

    test('initial sync caches records via a single cacheMany call', () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[
              {'id': 't1', 'status': 'active'},
              {'id': 't2', 'status': 'planned'},
            ],
            'cursor': 'c1',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      await service.sync(entityType: 'transport');

      expect(fakeDb.cacheManyCalls, hasLength(1));
      expect(fakeDb.cacheManyCalls.single.keys, containsAll(['t1', 't2']));
    });

    // ── Delta sync (with existing cursor) ───────────────────────────────

    test('delta sync uses stored cursor', () async {
      await fakeDb.write(
        'transport',
        'cursor-delta-99',
        namespace: 'sync_cursors',
      );

      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': '3'}],
            'cursor': 'cursor-delta-100',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      final result = await service.sync(entityType: 'transport');

      expect(fakeEndpoints.cursorCalls, ['cursor-delta-99']);
      expect(result.success, isTrue);
      expect(result.recordsSynced, 1);
    });

    test('delta sync updates cursor after success', () async {
      await fakeDb.write(
        'transport',
        'old-cursor',
        namespace: 'sync_cursors',
      );

      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': '42'}],
            'cursor': 'new-cursor',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      await service.sync(entityType: 'transport');

      expect(fakeDb.getStoredCursor('transport'), 'new-cursor');
    });

    // ── Multi-page / pagination ─────────────────────────────────────────

    test('multi-page sync accumulates all records with one cacheMany per page',
        () async {
      fakeEndpoints.returnsSyncEntityPages([
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': 'a'}, {'id': 'b'}],
            'cursor': 'p1',
            'has_more': true,
          },
          requestOptions: RequestOptions(path: ''),
        ),
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': 'c'}, {'id': 'd'}],
            'cursor': 'p2',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      ]);

      final result = await service.sync(entityType: 'transport');

      expect(result.success, isTrue);
      expect(result.recordsSynced, 4);
      // One batch write per page, never per record.
      expect(fakeDb.cacheManyCalls, hasLength(2));
      expect(fakeDb.cacheManyCalls[0].keys, containsAll(['a', 'b']));
      expect(fakeDb.cacheManyCalls[1].keys, containsAll(['c', 'd']));
      // Page 2's request echoes page 1's cursor verbatim.
      expect(fakeEndpoints.cursorCalls, [null, 'p1']);
    });

    test('opaque compound cursor round-trips verbatim into next since',
        () async {
      fakeEndpoints.returnsSyncEntityPages([
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': '1'}],
            'cursor': '2026-06-01T10:00:00Z|42',
            'has_more': true,
          },
          requestOptions: RequestOptions(path: ''),
        ),
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': '2'}],
            'cursor': '2026-06-01T10:00:01Z|9',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      ]);

      await service.sync(entityType: 'transport');

      expect(fakeEndpoints.cursorCalls, [null, '2026-06-01T10:00:00Z|42']);
      expect(fakeDb.getStoredCursor('transport'), '2026-06-01T10:00:01Z|9');
    });

    test('sync terminates when backend returns has_more forever (page cap)',
        () async {
      fakeEndpoints.returnsInfiniteHasMore();

      final result = await service.sync(entityType: 'transport');

      expect(result.success, isFalse);
      expect(result.error, contains('exceeded the maximum'));
      expect(
        fakeEndpoints.syncEntityCallCount,
        DeltaSyncService.maxPagesPerRun,
      );
      // Cap-hit persists the cursor from the last fetched page (page 50) so
      // the next run resumes instead of refetching the same pages.
      expect(await service.getLastCursor('transport'), 'cursor-x');
    });

    test('null cursor response is not persisted and next sync sends no since',
        () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': '1'}],
            'cursor': null,
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );
      await service.sync(entityType: 'transport');
      expect(fakeDb.getStoredCursor('transport'), isNull);

      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[],
            'cursor': null,
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );
      await service.sync(entityType: 'transport');

      // Neither sync sent a `since` cursor.
      expect(fakeEndpoints.cursorCalls, [null, null]);
    });

    // ── Multiple entity types ───────────────────────────────────────────

    test('syncs multiple entity types independently', () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': 't1'}],
            'cursor': 'cursor-transport',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );
      await service.sync(entityType: 'transport');
      expect(fakeDb.getStoredCursor('transport'), 'cursor-transport');

      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': 'm1'}],
            'cursor': 'cursor-message',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );
      final result = await service.sync(entityType: 'message');
      expect(fakeDb.getStoredCursor('message'), 'cursor-message');
      expect(result.recordsSynced, 1);
    });

    test('entity types have independent cursors', () async {
      await fakeDb.write('transport', 't-cursor', namespace: 'sync_cursors');
      await fakeDb.write('message', 'm-cursor', namespace: 'sync_cursors');

      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[],
            'cursor': 't-cursor-2',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );
      await service.sync(entityType: 'transport');

      expect(fakeDb.getStoredCursor('transport'), 't-cursor-2');
      expect(fakeDb.getStoredCursor('message'), 'm-cursor');
    });

    // ── Cursor management ───────────────────────────────────────────────

    test('getLastCursor returns null when no prior sync', () async {
      final cursor = await service.getLastCursor('transport');
      expect(cursor, isNull);
    });

    test('getLastCursor returns stored cursor after sync', () async {
      await fakeDb.write('transport', 'abc', namespace: 'sync_cursors');
      final cursor = await service.getLastCursor('transport');
      expect(cursor, 'abc');
    });

    test('getLastCursor returns correct cursor per entity type', () async {
      await fakeDb.write('transport', 't-cur', namespace: 'sync_cursors');
      await fakeDb.write('message', 'm-cur', namespace: 'sync_cursors');
      expect(await service.getLastCursor('transport'), 't-cur');
      expect(await service.getLastCursor('message'), 'm-cur');
    });

    test('updateCursor persists cursor', () async {
      await service.updateCursor('transport', 'my-cursor');
      final stored = await fakeDb.read(
        'transport',
        namespace: 'sync_cursors',
      );
      expect(stored, 'my-cursor');
    });

    test('updateCursor overwrites previous cursor', () async {
      await service.updateCursor('transport', 'first');
      await service.updateCursor('transport', 'second');
      final stored = await fakeDb.read(
        'transport',
        namespace: 'sync_cursors',
      );
      expect(stored, 'second');
    });

    test('updateCursor rethrows on failure', () async {
      final throwingDb = _ThrowingLocalDatabase();
      final throwingService = DeltaSyncService(fakeEndpoints, throwingDb);

      await expectLater(
        throwingService.updateCursor('x', 'y'),
        throwsA(isA<Exception>()),
      );
    });

    // ── Error handling ──────────────────────────────────────────────────

    test('sync returns error result on network failure', () async {
      fakeEndpoints.throwsOnSyncEntity(Exception('Network unreachable'));

      final result = await service.sync(entityType: 'transport');

      expect(result.success, isFalse);
      expect(result.recordsSynced, 0);
      expect(result.error, isNotNull);
      expect(result.error, contains('Network unreachable'));
    });

    test('sync returns error result on unexpected response format (null body)',
        () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: null,
          requestOptions: RequestOptions(path: ''),
        ),
      );

      final result = await service.sync(entityType: 'transport');

      expect(result.success, isFalse);
      expect(result.recordsSynced, 0);
    });

    test('sync returns error result on unexpected response format (string body)',
        () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: 'just a string',
          requestOptions: RequestOptions(path: ''),
        ),
      );

      final result = await service.sync(entityType: 'transport');

      expect(result.success, isFalse);
      expect(result.recordsSynced, 0);
      expect(result.error, contains('Unexpected response format'));
    });

    test('sync returns error result on DioException', () async {
      fakeEndpoints.throwsOnSyncEntity(
        DioException(
          requestOptions: RequestOptions(path: ''),
          type: DioExceptionType.connectionTimeout,
        ),
      );

      final result = await service.sync(entityType: 'transport');

      expect(result.success, isFalse);
      expect(result.recordsSynced, 0);
      expect(result.error, isNotNull);
      expect(result.error, contains('DioException'));
    });

    test('sync does not update cursor on error', () async {
      fakeEndpoints.throwsOnSyncEntity(Exception('Fail'));

      await service.sync(entityType: 'transport');

      expect(fakeDb.getStoredCursor('transport'), isNull);
    });

    test('sync does not cache records on error', () async {
      fakeEndpoints.throwsOnSyncEntity(Exception('Fail'));

      await service.sync(entityType: 'transport');

      expect(fakeDb.cacheManyCalls, isEmpty);
    });

    test('malformed response (missing records list) is a failure', () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {'cursor': 'c3'},
          requestOptions: RequestOptions(path: ''),
        ),
      );

      final result = await service.sync(entityType: 'transport');

      expect(result.success, isFalse);
      expect(result.error, contains('records'));
    });

    test('malformed response (records not a list) is a failure', () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': 'not a list',
            'cursor': 'c4',
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      final result = await service.sync(entityType: 'transport');

      expect(result.success, isFalse);
      expect(result.error, contains('records'));
    });

    // ── Edge cases ──────────────────────────────────────────────────────

    test('sync with empty records list returns success with zero count',
        () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[],
            'cursor': 'cursor-empty',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      final result = await service.sync(entityType: 'transport');

      expect(result.success, isTrue);
      expect(result.recordsSynced, 0);
      expect(fakeDb.getStoredCursor('transport'), 'cursor-empty');
    });

    test('sync handles records with _id instead of id', () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[
              {'_id': 'doc-99', 'title': 'Doc'},
            ],
            'cursor': 'c2',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      final result = await service.sync(entityType: 'document');

      expect(result.success, isTrue);
      expect(fakeDb.cacheManyCalls, hasLength(1));
      expect(fakeDb.cacheManyCalls.single.keys, contains('doc-99'));
    });

    test('sync skips non-map entries in records list', () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <dynamic>[
              {'id': 'valid1'},
              'just a string',
              {'id': 'valid2'},
              42,
            ],
            'cursor': 'c5',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      final result = await service.sync(entityType: 'transport');

      expect(result.success, isTrue);
      // Only map entries count as synced records.
      expect(result.recordsSynced, 2);
      expect(fakeDb.cacheManyCalls, hasLength(1));
      expect(
        fakeDb.cacheManyCalls.single.keys,
        containsAll(['valid1', 'valid2']),
      );
    });

    // ── Full sync ───────────────────────────────────────────────────────

    test('fullSync returns all records', () async {
      fakeEndpoints.returnsSyncEntityPages([
        Response(
          data: {
            'records': <Map<String, dynamic>>[
              {'id': 'a1'},
              {'id': 'a2'},
              {'id': 'a3'},
            ],
            'cursor': 'full-cursor',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      ]);

      final result = await service.fullSync(entityType: 'transport');

      expect(result.success, isTrue);
      expect(result.recordsSynced, 3);
    });

    test('fullSync updates cursor', () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': 'x'}],
            'cursor': 'full-cursor-xyz',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      await service.fullSync(entityType: 'transport');

      expect(fakeDb.getStoredCursor('transport'), 'full-cursor-xyz');
    });

    test('fullSync ignores stored cursor and starts from page 1', () async {
      await fakeDb.write('transport', 'stored-cursor', namespace: 'sync_cursors');

      fakeEndpoints.returnsSyncEntityPages([
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': 'a'}],
            'cursor': 'full1',
            'has_more': true,
          },
          requestOptions: RequestOptions(path: ''),
        ),
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': 'b'}],
            'cursor': 'full2',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      ]);

      final result = await service.fullSync(entityType: 'transport');

      // No `since` on the first page despite the stored cursor.
      expect(fakeEndpoints.cursorCalls, [null, 'full1']);
      expect(result.success, isTrue);
      expect(result.recordsSynced, 2);
      expect(fakeDb.getStoredCursor('transport'), 'full2');
    });

    test('fullSync returns error on network failure', () async {
      fakeEndpoints.throwsOnSyncEntity(Exception('Server 500'));

      final result = await service.fullSync(entityType: 'transport');

      expect(result.success, isFalse);
      expect(result.recordsSynced, 0);
      expect(result.error, contains('Server 500'));
    });

    test('fullSync with null cursor in response still returns success',
        () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': 'r1'}],
            'cursor': null,
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      final result = await service.fullSync(entityType: 'transport');

      expect(result.success, isTrue);
      expect(result.recordsSynced, 1);
    });

    test('fullSync overwrites existing delta cursor', () async {
      await fakeDb.write('transport', 'delta-cursor', namespace: 'sync_cursors');

      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': 'r1'}],
            'cursor': 'full-cursor',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      await service.fullSync(entityType: 'transport');

      expect(fakeDb.getStoredCursor('transport'), 'full-cursor');
    });

    // ── Consecutive syncs ───────────────────────────────────────────────

    test('two consecutive syncs use updated cursor', () async {
      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': '1'}],
            'cursor': 'cursor-1',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      await service.sync(entityType: 'transport');
      expect(fakeEndpoints.cursorCalls, [null]); // first sync: no cursor

      fakeEndpoints.returnsSyncEntity(
        Response(
          data: {
            'records': <Map<String, dynamic>>[{'id': '2'}],
            'cursor': 'cursor-2',
            'has_more': false,
          },
          requestOptions: RequestOptions(path: ''),
        ),
      );

      await service.sync(entityType: 'transport');
      expect(fakeEndpoints.cursorCalls, [null, 'cursor-1']);
    });
  });
}

// =============================================================================
// Helper: LocalDatabase that throws on write
// =============================================================================

class _ThrowingLocalDatabase implements LocalDatabase {
  @override
  Future<void> initialize() async {}

  @override
  Future<void> write(String key, dynamic value, {String namespace = 'default'}) async {
    throw Exception('Write failed');
  }

  @override
  Future<dynamic> read(String key, {String namespace = 'default'}) async => null;

  @override
  Future<void> delete(String key, {String namespace = 'default'}) async {}

  @override
  Future<List<String>> keysWithPrefix(String prefix, {String namespace = 'default'}) async => [];

  @override
  Future<void> deleteAllWithPrefix(String prefix, {String namespace = 'default'}) async {}

  @override
  Future<void> cacheData(String collection, String key, Map<String, dynamic> data) async {}

  @override
  Future<void> cacheMany(
    String collection,
    Map<String, Map<String, dynamic>> records,
  ) async {}

  @override
  Future<Map<String, dynamic>?> getCachedData(String collection, String key) async => null;

  @override
  Future<void> cacheTransports(List<Map<String, dynamic>> transports) async {}

  @override
  Future<List<Map<String, dynamic>>> getCachedTransports() async => [];

  @override
  Future<void> clearCollection(String collection) async {}

  @override
  Future<List<Map<String, dynamic>>> getAllCachedData(String collection) async => [];

  @override
  Future<void> close() async {}
}
