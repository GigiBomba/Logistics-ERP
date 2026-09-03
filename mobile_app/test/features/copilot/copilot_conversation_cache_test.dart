import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/core/storage/local_db.dart';
import 'package:operion_mobile/features/copilot/storage/copilot_conversation_cache.dart';

// ─────────────────────────────────────────────────────────────────────────────
// In-memory LocalDatabase fake: same public surface the cache uses, no disk I/O.
// ─────────────────────────────────────────────────────────────────────────────

class _InMemoryLocalDatabase extends LocalDatabase {
  final Map<String, Map<String, dynamic>> _store = {};

  @override
  Future<void> initialize() async {}

  @override
  Future<dynamic> read(String key, {String namespace = 'default'}) async {
    return _store[namespace]?[key];
  }

  @override
  Future<void> write(
    String key,
    dynamic value, {
    String namespace = 'default',
  }) async {
    _store.putIfAbsent(namespace, () => {})[key] = value;
  }

  @override
  Future<List<String>> keysWithPrefix(
    String prefix, {
    String namespace = 'default',
  }) async {
    final keys = _store[namespace]?.keys ?? const <String>[];
    return keys.where((k) => k.startsWith(prefix)).toList();
  }

  @override
  Future<void> delete(String key, {String namespace = 'default'}) async {
    _store[namespace]?.remove(key);
  }

  @override
  Future<void> deleteAllWithPrefix(
    String prefix, {
    String namespace = 'default',
  }) async {
    _store[namespace]?.removeWhere((k, _) => k.startsWith(prefix));
  }
}

Map<String, dynamic> _seededEntry(String cachedAt) => {
      'data': <String, dynamic>{'conversation_id': 'x', 'messages': <dynamic>[]},
      'cached_at': cachedAt,
      'is_offline': true,
      'is_read_only': true,
    };

void main() {
  group('CopilotConversationCache', () {
    late _InMemoryLocalDatabase db;

    setUp(() async {
      db = _InMemoryLocalDatabase();
      await db.initialize();
    });

    group('conversation list', () {
      test('caches and reads back a conversation list with offline flag',
          () async {
        final cache = CopilotConversationCache(db);
        final payload = <String, dynamic>{
          'items': <dynamic>[
            <String, dynamic>{'id': 'conv-1', 'title': 'First'},
            <String, dynamic>{'id': 'conv-2', 'title': 'Second'},
          ],
          'next_cursor': null,
        };

        await cache.cacheConversations(payload);
        final cached = await cache.readCachedConversations();

        expect(cached, isNotNull);
        expect(cached!.isOffline, isTrue);
        expect(cached.isReadOnly, isTrue);
        expect(cached.data['items'], hasLength(2));
        expect(cached.cachedAt.isBefore(DateTime.now()), isTrue);
      });

      test('returns null when nothing cached', () async {
        final cache = CopilotConversationCache(db);
        expect(await cache.readCachedConversations(), isNull);
      });

      test('returns null for an expired entry', () async {
        final cache = CopilotConversationCache(db, ttl: const Duration(days: 7));
        final stale = CachedCopilotConversation(
          data: <String, dynamic>{'items': <dynamic>[]},
          cachedAt: DateTime.now().subtract(const Duration(days: 30)),
        );
        await db.write(
          'conversations',
          stale.toJson(),
          namespace: CopilotConversationCache.namespace,
        );

        expect(await cache.readCachedConversations(), isNull);
      });

      test('returns the entry when within TTL', () async {
        final cache = CopilotConversationCache(db, ttl: const Duration(days: 7));
        final fresh = CachedCopilotConversation(
          data: <String, dynamic>{'items': <dynamic>[]},
          cachedAt: DateTime.now().subtract(const Duration(days: 1)),
        );
        await db.write(
          'conversations',
          fresh.toJson(),
          namespace: CopilotConversationCache.namespace,
        );

        final cached = await cache.readCachedConversations();
        expect(cached, isNotNull);
      });
    });

    group('single conversation (message history)', () {
      test('caches and reads back a conversation', () async {
        final cache = CopilotConversationCache(db);
        final payload = <String, dynamic>{
          'conversation_id': 'conv-9',
          'messages': <dynamic>[],
        };

        await cache.cacheConversation('conv-9', payload);
        final cached = await cache.readCachedConversation('conv-9');

        expect(cached, isNotNull);
        expect(cached!.isOffline, isTrue);
        expect(cached.isReadOnly, isTrue);
        expect(cached.data['conversation_id'], 'conv-9');
      });

      test('returns null when not cached', () async {
        final cache = CopilotConversationCache(db);
        expect(await cache.readCachedConversation('nope'), isNull);
      });
    });

    group('bounded size', () {
      test('evicts the oldest conversations beyond maxConversations', () async {
        final cache = CopilotConversationCache(db, maxConversations: 2);
        // Seed three conversations with distinct timestamps.
        await db.write(
          'conversation:a',
          _seededEntry('2026-01-01T00:00:00.000'),
          namespace: CopilotConversationCache.namespace,
        );
        await db.write(
          'conversation:b',
          _seededEntry('2026-01-02T00:00:00.000'),
          namespace: CopilotConversationCache.namespace,
        );
        await db.write(
          'conversation:c',
          _seededEntry('2026-01-03T00:00:00.000'),
          namespace: CopilotConversationCache.namespace,
        );

        // Trigger a trim through a normal cache write.
        await cache.cacheConversations(<String, dynamic>{'items': <dynamic>[]});

        final keys = await db.keysWithPrefix(
          'conversation:',
          namespace: CopilotConversationCache.namespace,
        );
        expect(keys, hasLength(2));
        expect(keys, isNot(contains('conversation:a')));
        expect(keys, containsAll(<String>['conversation:b', 'conversation:c']));
      });
    });

    group('clear', () {
      test('removes every cached entry', () async {
        final cache = CopilotConversationCache(db);
        await cache.cacheConversations(<String, dynamic>{'items': <dynamic>[]});
        await cache.cacheConversation(
          'conv-1',
          <String, dynamic>{'conversation_id': 'conv-1'},
        );

        await cache.clear();

        expect(await cache.readCachedConversations(), isNull);
        expect(await cache.readCachedConversation('conv-1'), isNull);
      });
    });
  });

  group('CachedCopilotConversation', () {
    test('isExpired detects TTL expiry against a fixed clock', () {
      final cached = CachedCopilotConversation(
        data: const <String, dynamic>{},
        cachedAt: DateTime(2026, 1, 1),
      );
      expect(
        cached.isExpired(DateTime(2026, 1, 2), const Duration(days: 7)),
        isFalse,
      );
      expect(
        cached.isExpired(DateTime(2026, 1, 20), const Duration(days: 7)),
        isTrue,
      );
    });

    test('toJson/fromJson roundtrip preserves the offline flag', () {
      final cached = CachedCopilotConversation(
        data: <String, dynamic>{'items': <dynamic>[]},
        cachedAt: DateTime(2026, 1, 1),
      );

      final restored = CachedCopilotConversation.fromJson(cached.toJson());

      expect(restored.isOffline, isTrue);
      expect(restored.isReadOnly, isTrue);
      expect(restored.cachedAt, DateTime(2026, 1, 1));
      expect(restored.data['items'], isEmpty);
    });

    test('fromJson defaults missing data to an empty map', () {
      final restored = CachedCopilotConversation.fromJson(const <String, dynamic>{
        'cached_at': '2026-01-01T00:00:00.000',
      });
      expect(restored.data, isEmpty);
      expect(restored.isOffline, isTrue);
      expect(restored.isReadOnly, isTrue);
    });
  });
}