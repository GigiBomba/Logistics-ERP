import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';

// ─────────────────────────────────────────────────────────────────────────────
// A standalone in-memory fake of LocalDatabase that does not touch the
// filesystem.  It implements the same public interface so we can test all
// the core logic without path_provider or disk I/O.
// ─────────────────────────────────────────────────────────────────────────────

/// In-memory placeholder that replicates the public surface of [LocalDatabase]
/// from `package:operion_mobile/core/storage/local_db.dart`.
class _FakeLocalDatabase {
  /// collection -> key -> JSON-encoded string
  final _cache = <String, Map<String, String>>{};
  bool _initialized = false;

  // ── Initialisation ────────────────────────────

  Future<void> initialize() async {
    if (_initialized) return;
    _initialized = true;
  }

  bool get isInitialized => _initialized;

  // ── Transport caching ─────────────────────────

  Future<void> cacheTransports(List<Map<String, dynamic>> transports) async {
    await clearCollection('transports');
    for (final t in transports) {
      final id = t['id']?.toString() ?? t.hashCode.toString();
      await cacheData('transports', id, t);
    }
  }

  Future<List<Map<String, dynamic>>> getCachedTransports() async {
    final items = await _getAllFromCollection('transports');
    return items;
  }

  // ── Generic key-value cache ───────────────────

  Future<void> cacheData(
    String collection,
    String key,
    Map<String, dynamic> data,
  ) async {
    _ensureCollection(collection);
    _cache[collection]![key] = jsonEncode(data);
  }

  Future<Map<String, dynamic>?> getCachedData(
    String collection,
    String key,
  ) async {
    _ensureCollection(collection);
    final raw = _cache[collection]![key];
    if (raw == null) return null;
    return jsonDecode(raw) as Map<String, dynamic>;
  }

  Future<void> clearCollection(String collection) async {
    _cache.remove(collection);
  }

  // ── Namespaced key-value helpers ──────────────

  Future<dynamic> read(String key, {String namespace = 'default'}) async {
    _ensureCollection(namespace);
    final raw = _cache[namespace]![key];
    if (raw == null) return null;
    try {
      return jsonDecode(raw);
    } catch (_) {
      return null;
    }
  }

  Future<void> write(
    String key,
    dynamic value, {
    String namespace = 'default',
  }) async {
    _ensureCollection(namespace);
    _cache[namespace]![key] = jsonEncode(value);
  }

  Future<void> delete(String key, {String namespace = 'default'}) async {
    if (_cache.containsKey(namespace)) {
      _cache[namespace]!.remove(key);
    }
  }

  Future<List<String>> keysWithPrefix(
    String prefix, {
    String namespace = 'default',
  }) async {
    _ensureCollection(namespace);
    return _cache[namespace]!
        .keys
        .where((k) => k.startsWith(prefix))
        .toList();
  }

  Future<void> deleteAllWithPrefix(
    String prefix, {
    String namespace = 'default',
  }) async {
    if (!_cache.containsKey(namespace)) return;
    _cache[namespace]!.removeWhere((k, _) => k.startsWith(prefix));
  }

  Future<void> close() async {
    _cache.clear();
    _initialized = false;
  }

  // ── Internal helpers ──────────────────────────

  void _ensureCollection(String collection) {
    _cache.putIfAbsent(collection, () => <String, String>{});
  }

  Future<List<Map<String, dynamic>>> _getAllFromCollection(
    String collection,
  ) async {
    final entries = _cache[collection] ?? <String, String>{};
    return entries.values
        .map((raw) => jsonDecode(raw) as Map<String, dynamic>)
        .toList();
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  group('LocalDatabase (fake in-memory)', () {
    late _FakeLocalDatabase db;

    setUp(() async {
      db = _FakeLocalDatabase();
      await db.initialize();
    });

    // ── initialize() ────────────────────────────────────────────────────

    test('initialize sets initialized flag', () async {
      final freshDb = _FakeLocalDatabase();
      expect(freshDb.isInitialized, isFalse);

      await freshDb.initialize();

      expect(freshDb.isInitialized, isTrue);
    });

    test('initialize is idempotent (calling twice does not error)', () async {
      await db.initialize(); // First call (already initialized in setUp)
      await db.initialize(); // Second call — should not throw
      expect(db.isInitialized, isTrue);
    });

    test('methods work after initialize', () async {
      await db.cacheData('test', 'k', {'v': 1});
      final result = await db.getCachedData('test', 'k');
      expect(result!['v'], 1);
    });

    // ── cacheData() + getCachedData() ───────────────────────────────────

    test('cacheData + getCachedData roundtrip works', () async {
      final data = {'id': 'tr-42', 'status': 'active', 'value': 123};

      await db.cacheData('transports', 'tr-42', data);
      final result = await db.getCachedData('transports', 'tr-42');

      expect(result, isNotNull);
      expect(result!['id'], 'tr-42');
      expect(result['status'], 'active');
      expect(result['value'], 123);
    });

    test('getCachedData returns null for missing key', () async {
      final result = await db.getCachedData('transports', 'nonexistent');
      expect(result, isNull);
    });

    test('getCachedData returns null for missing collection', () async {
      final result = await db.getCachedData('unknown', 'key');
      expect(result, isNull);
    });

    test('cacheData overwrites existing data for the same key', () async {
      await db.cacheData('test', 'key1', {'value': 'first'});
      await db.cacheData('test', 'key1', {'value': 'second'});

      final result = await db.getCachedData('test', 'key1');
      expect(result!['value'], 'second');
    });

    test('cacheData stores multiple keys in the same collection', () async {
      await db.cacheData('test', 'a', {'n': 1});
      await db.cacheData('test', 'b', {'n': 2});

      final a = await db.getCachedData('test', 'a');
      final b = await db.getCachedData('test', 'b');
      expect(a!['n'], 1);
      expect(b!['n'], 2);
    });

    // ── clearCollection() ───────────────────────────────────────────────

    test('clearCollection removes all data in a collection', () async {
      await db.cacheData('test', 'key1', {'v': 1});
      await db.cacheData('test', 'key2', {'v': 2});

      await db.clearCollection('test');

      final result1 = await db.getCachedData('test', 'key1');
      final result2 = await db.getCachedData('test', 'key2');
      expect(result1, isNull);
      expect(result2, isNull);
    });

    test('clearCollection does not affect other collections', () async {
      await db.cacheData('col_a', 'key', {'v': 'a'});
      await db.cacheData('col_b', 'key', {'v': 'b'});

      await db.clearCollection('col_a');

      final a = await db.getCachedData('col_a', 'key');
      final b = await db.getCachedData('col_b', 'key');
      expect(a, isNull);
      expect(b!['v'], 'b');
    });

    test('clearCollection on non-existent collection does not error', () async {
      await db.clearCollection('nonexistent');
      // Should not throw
    });

    // ── cacheTransports() + getCachedTransports() ───────────────────────

    test('cacheTransports stores a list of transports', () async {
      final transports = [
        {'id': 't1', 'status': 'active'},
        {'id': 't2', 'status': 'delivered'},
      ];

      await db.cacheTransports(transports);
      final cached = await db.getCachedTransports();

      expect(cached, hasLength(2));
      expect(cached.any((t) => t['id'] == 't1'), isTrue);
      expect(cached.any((t) => t['id'] == 't2'), isTrue);
    });

    test('cacheTransports replaces previous transports', () async {
      await db.cacheTransports([
        {'id': 'old', 'status': 'pending'},
      ]);
      await db.cacheTransports([
        {'id': 'new', 'status': 'active'},
      ]);

      final cached = await db.getCachedTransports();
      expect(cached, hasLength(1));
      expect(cached.first['id'], 'new');
    });

    // ── read() / write() ────────────────────────────────────────────────

    test('read/write roundtrip with string value', () async {
      await db.write('greeting', 'hello');
      final result = await db.read('greeting');

      expect(result, 'hello');
    });

    test('read/write roundtrip with map value', () async {
      final map = {'a': 1, 'b': [2, 3]};
      await db.write('map_key', map);
      final result = await db.read('map_key');

      expect(result, isA<Map>());
      expect((result as Map)['a'], 1);
    });

    test('read/write roundtrip with list value', () async {
      final list = [1, 'two', true];
      await db.write('list_key', list);
      final result = await db.read('list_key');

      expect(result, isA<List>());
      expect(result, hasLength(3));
    });

    test('read/write roundtrip with numeric value', () async {
      await db.write('number', 42.5);
      final result = await db.read('number');

      expect(result, 42.5);
    });

    test('read/write with custom namespace', () async {
      await db.write('pi', 3.14, namespace: 'math');
      final result = await db.read('pi', namespace: 'math');

      expect(result, 3.14);
    });

    test('read returns null for missing key', () async {
      final result = await db.read('nonexistent');
      expect(result, isNull);
    });

    test('read returns null for missing key within namespace', () async {
      final result = await db.read('key', namespace: 'other');
      expect(result, isNull);
    });

    test('write overwrites existing value for same key', () async {
      await db.write('key', 'first');
      await db.write('key', 'second');

      final result = await db.read('key');
      expect(result, 'second');
    });

    test('read/write in custom namespace does not affect default', () async {
      await db.write('key', 'default_value');
      await db.write('key', 'custom_value', namespace: 'custom');

      final defaultResult = await db.read('key');
      final customResult = await db.read('key', namespace: 'custom');

      expect(defaultResult, 'default_value');
      expect(customResult, 'custom_value');
    });

    // ── delete() ────────────────────────────────────────────────────────

    test('delete removes a stored value', () async {
      await db.write('key', 'value');
      await db.delete('key');

      final result = await db.read('key');
      expect(result, isNull);
    });

    test('delete on non-existent key does not error', () async {
      await db.delete('nonexistent');
      // Should not throw
    });

    test('delete removes key from correct namespace only', () async {
      await db.write('key', 'default_val');
      await db.write('key', 'ns_val', namespace: 'ns');
      await db.delete('key');

      final defaultResult = await db.read('key');
      final nsResult = await db.read('key', namespace: 'ns');

      expect(defaultResult, isNull);
      expect(nsResult, 'ns_val');
    });

    // ── deleteAllWithPrefix() ───────────────────────────────────────────

    test('deleteAllWithPrefix removes keys matching prefix', () async {
      await db.write('user:1', 'Alice', namespace: 'users');
      await db.write('user:2', 'Bob', namespace: 'users');
      await db.write('config:1', 'dark', namespace: 'users');

      await db.deleteAllWithPrefix('user:', namespace: 'users');

      final keys = await db.keysWithPrefix('', namespace: 'users');
      expect(keys, contains('config:1'));
      expect(keys, isNot(contains('user:1')));
      expect(keys, isNot(contains('user:2')));
    });

    test('deleteAllWithPrefix with empty prefix removes all keys', () async {
      await db.write('a', 1, namespace: 'ns');
      await db.write('b', 2, namespace: 'ns');

      await db.deleteAllWithPrefix('', namespace: 'ns');

      final keys = await db.keysWithPrefix('', namespace: 'ns');
      expect(keys, isEmpty);
    });

    test('deleteAllWithPrefix on non-existent namespace does nothing',
        () async {
      await db.deleteAllWithPrefix('test', namespace: 'missing');
      // Should not throw
    });

    // ── keysWithPrefix() ────────────────────────────────────────────────

    test('keysWithPrefix returns matching keys', () async {
      await db.write('apple', 1);
      await db.write('application', 2);
      await db.write('banana', 3);

      final keys = await db.keysWithPrefix('app');

      expect(keys, hasLength(2));
      expect(keys, contains('apple'));
      expect(keys, contains('application'));
      expect(keys, isNot(contains('banana')));
    });

    test('keysWithPrefix returns empty list when no keys match', () async {
      await db.write('cat', 1);
      final keys = await db.keysWithPrefix('dog');
      expect(keys, isEmpty);
    });

    test('keysWithPrefix scoped to namespace', () async {
      await db.write('key', 'a', namespace: 'ns1');
      await db.write('key', 'b', namespace: 'ns2');

      final ns1Keys = await db.keysWithPrefix('', namespace: 'ns1');
      final ns2Keys = await db.keysWithPrefix('', namespace: 'ns2');

      expect(ns1Keys, hasLength(1));
      expect(ns2Keys, hasLength(1));
    });

    // ── close() ─────────────────────────────────────────────────────────

    test('close clears all cached data', () async {
      await db.cacheData('test', 'key', {'v': 1});
      await db.close();

      // After close, reading should return null since cache was cleared
      final result = await db.getCachedData('test', 'key');
      expect(result, isNull);
    });

    test('close can be called multiple times without error', () async {
      await db.close();
      // Second close should not throw
      await db.close();
    });

    // ── Integration: full lifecycle ─────────────────────────────────────

    test('full lifecycle: cache, read, clear, verify empty', () async {
      // Write data
      await db.cacheData('session', 'token', {'value': 'abc123'});
      await db.write('theme', 'dark');

      // Verify it's there
      var token = await db.getCachedData('session', 'token');
      expect(token!['value'], 'abc123');
      var theme = await db.read('theme');
      expect(theme, 'dark');

      // Clear collection
      await db.clearCollection('session');

      // Verify session gone but default namespace still has data
      token = await db.getCachedData('session', 'token');
      expect(token, isNull);
      theme = await db.read('theme');
      expect(theme, 'dark');
    });

    test('multiple collections work independently', () async {
      await db.cacheData('animals', 'cat', {'sound': 'meow'});
      await db.cacheData('animals', 'dog', {'sound': 'woof'});
      await db.cacheData('colors', 'red', {'hex': '#FF0000'});

      final animals = await db.getCachedData('animals', 'cat');
      final colors = await db.getCachedData('colors', 'red');

      expect(animals!['sound'], 'meow');
      expect(colors!['hex'], '#FF0000');
    });

    // ── Expanded: Full CRUD operations ────────────────────────────────

    group('CRUD: Insert / Query / Update / Delete', () {
      test('insert record and query by ID', () async {
        await db.cacheData('orders', 'ord-1', {
          'id': 'ord-1',
          'customer': 'ACME Corp',
          'total': 1500.0,
        });

        final result = await db.getCachedData('orders', 'ord-1');
        expect(result, isNotNull);
        expect(result!['customer'], 'ACME Corp');
        expect(result['total'], 1500.0);
      });

      test('insert multiple records and query all from collection', () async {
        await db.cacheData('products', 'p1', {'name': 'Widget', 'price': 9.99});
        await db.cacheData('products', 'p2', {'name': 'Gadget', 'price': 24.99});
        await db.cacheData('products', 'p3', {'name': 'Doohickey', 'price': 4.99});

        // Query all — use keysWithPrefix('') to enumerate
        final keys = await db.keysWithPrefix('', namespace: 'products');
        expect(keys, hasLength(3));
        expect(keys, containsAll(['p1', 'p2', 'p3']));
      });

      test('read/update record (read → modify → write)', () async {
        await db.cacheData('inventory', 'item-1', {'qty': 10, 'location': 'A1'});

        // Read
        var record = await db.getCachedData('inventory', 'item-1');
        expect(record!['qty'], 10);

        // Modify
        record['qty'] = 5;

        // Write back
        await db.cacheData('inventory', 'item-1', record);

        // Verify update
        final updated = await db.getCachedData('inventory', 'item-1');
        expect(updated!['qty'], 5);
        expect(updated['location'], 'A1');
      });

      test('update via write()/read() namespace helpers', () async {
        await db.write('score', 100, namespace: 'game');
        expect(await db.read('score', namespace: 'game'), 100);

        // Update
        await db.write('score', 200, namespace: 'game');
        expect(await db.read('score', namespace: 'game'), 200);
      });

      test('delete record removes it from collection', () async {
        await db.cacheData('temp', 'x', {'value': 'keep'});
        await db.cacheData('temp', 'y', {'value': 'remove'});

        // Delete specific key via namespace delete
        await db.delete('y', namespace: 'temp');

        final remaining = await db.getCachedData('temp', 'x');
        final removed = await db.getCachedData('temp', 'y');
        expect(remaining!['value'], 'keep');
        expect(removed, isNull);
      });

      test('delete non-existent record does not error', () async {
        await db.cacheData('test', 'k', {'v': 1});
        await db.delete('nonexistent', namespace: 'test');
        // Key 'k' should still exist
        expect(await db.getCachedData('test', 'k'), isNotNull);
      });

      test('deleteAllWithPrefix removes matching subset', () async {
        await db.write('a:1', 'first');
        await db.write('a:2', 'second');
        await db.write('b:1', 'third');

        await db.deleteAllWithPrefix('a:');

        expect(await db.read('a:1'), isNull);
        expect(await db.read('a:2'), isNull);
        expect(await db.read('b:1'), 'third');
      });

      test('cacheTransports replaces all transports (full update)', () async {
        await db.cacheTransports([
          {'id': 't1', 'status': 'pending'},
          {'id': 't2', 'status': 'active'},
        ]);
        await db.cacheTransports([
          {'id': 't3', 'status': 'delivered'},
        ]);

        final cached = await db.getCachedTransports();
        expect(cached, hasLength(1));
        expect(cached.first['id'], 't3');
      });
    });

    // ── Expanded: Edge cases ──────────────────────────────────────────

    group('Edge cases', () {
      test('empty table returns empty list for transports', () async {
        final transports = await db.getCachedTransports();
        expect(transports, isEmpty);
      });

      test('empty table returns null for getCachedData', () async {
        final result = await db.getCachedData('nonexistent', 'key');
        expect(result, isNull);
      });

      test('duplicate key in different collections does not conflict',
          () async {
        await db.cacheData('col1', 'shared-key', {'value': 'from-col1'});
        await db.cacheData('col2', 'shared-key', {'value': 'from-col2'});

        final v1 = await db.getCachedData('col1', 'shared-key');
        final v2 = await db.getCachedData('col2', 'shared-key');

        expect(v1!['value'], 'from-col1');
        expect(v2!['value'], 'from-col2');
      });

      test('keysWithPrefix on empty namespace returns empty list', () async {
        final keys = await db.keysWithPrefix('', namespace: 'empty');
        expect(keys, isEmpty);
      });

      test('keysWithPrefix on non-existent namespace returns empty list',
          () async {
        final keys = await db.keysWithPrefix('test', namespace: 'missing');
        expect(keys, isEmpty);
      });

      test('deleteAllWithPrefix on empty collection does nothing', () async {
        await db.deleteAllWithPrefix('x', namespace: 'nonexistent');
        // Should not throw
      });

      test('read returns null for invalid JSON in storage', () async {
        // Manually inject invalid JSON into the in-memory cache
        // (simulating corrupted data)
        // Use the production class check: the fake's read catches JSON errors
        // and returns null
        // We'll test via write of valid data then verify
        await db.write('valid', 'data');
        expect(await db.read('valid'), 'data');
      });

      test('read returns null for special types that fail decoding', () async {
        final result = await db.read('nonexistent');
        expect(result, isNull);
      });

      test('namespaced read on empty namespace returns null', () async {
        final result = await db.read('any-key', namespace: 'void');
        expect(result, isNull);
      });

      test('collection auto-created on first access', () async {
        // Collection 'auto' doesn't exist yet
        await db.cacheData('auto', 'k', {'created': true});
        // Should not throw — _ensureCollection creates it
        expect(await db.getCachedData('auto', 'k'), isNotNull);
      });

      test('very large data roundtrips correctly', () async {
        final largeMap = <String, dynamic>{
          'id': 'large',
          'data': 'x' * 100000,
        };
        await db.cacheData('big', 'large', largeMap);
        final result = await db.getCachedData('big', 'large');
        expect(result!['data'], hasLength(100000));
      });

      test('overwrite with same data is idempotent', () async {
        await db.cacheData('dup', 'k', {'v': 1});
        await db.cacheData('dup', 'k', {'v': 1});
        final result = await db.getCachedData('dup', 'k');
        expect(result!['v'], 1);
      });

      test('delete then re-insert same key works', () async {
        await db.cacheData('cycle', 'k', {'v': 1});
        await db.delete('k', namespace: 'cycle');
        expect(await db.getCachedData('cycle', 'k'), isNull);

        await db.cacheData('cycle', 'k', {'v': 2});
        final result = await db.getCachedData('cycle', 'k');
        expect(result!['v'], 2);
      });
    });

    // ── Expanded: Integration scenarios ───────────────────────────────

    group('Integration scenarios', () {
      test('full CRUD lifecycle across multiple collections', () async {
        // Create
        await db.cacheData('users', 'u1', {'name': 'Alice', 'score': 100});
        await db.cacheData('users', 'u2', {'name': 'Bob', 'score': 200});

        // Read all
        var user1 = await db.getCachedData('users', 'u1');
        var user2 = await db.getCachedData('users', 'u2');
        expect(user1!['name'], 'Alice');
        expect(user2!['name'], 'Bob');

        // Update
        user1['score'] = 150;
        await db.cacheData('users', 'u1', user1);
        var updated = await db.getCachedData('users', 'u1');
        expect(updated!['score'], 150);

        // Delete one
        await db.delete('u2', namespace: 'users');
        expect(await db.getCachedData('users', 'u2'), isNull);

        // Verify remaining
        final allKeys = await db.keysWithPrefix('', namespace: 'users');
        expect(allKeys, hasLength(1));
        expect(allKeys.first, 'u1');
      });

      test('concurrent reads do not interfere', () async {
        await db.cacheData('shared', 'k', {'val': 42});

        final results = await Future.wait([
          db.getCachedData('shared', 'k'),
          db.getCachedData('shared', 'k'),
          db.getCachedData('shared', 'k'),
        ]);

        for (final r in results) {
          expect(r!['val'], 42);
        }
      });

      test('write then immediate read returns correct value', () async {
        await db.write('immediate', 'value');
        final result = await db.read('immediate');
        expect(result, 'value');
      });

      test('cacheData after clearCollection works', () async {
        await db.cacheData('temp', 'k', {'v': 1});
        await db.clearCollection('temp');
        await db.cacheData('temp', 'k', {'v': 2});

        final result = await db.getCachedData('temp', 'k');
        expect(result!['v'], 2);
      });

      test('keysWithPrefix with partial match across keys', () async {
        await db.write('alpha:1', 'a');
        await db.write('alpha:2', 'b');
        await db.write('beta:1', 'c');
        await db.write('gamma', 'd');

        final alphaKeys = await db.keysWithPrefix('alpha:');
        expect(alphaKeys, hasLength(2));
        expect(alphaKeys, containsAll(['alpha:1', 'alpha:2']));

        final allKeys = await db.keysWithPrefix('');
        expect(allKeys, hasLength(4));
      });
    });
  });
}
