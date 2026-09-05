import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/copilot_endpoints.dart';
import 'package:operion_mobile/core/storage/local_db.dart';
import 'package:operion_mobile/core/sync/action_queue.dart';
import 'package:operion_mobile/features/copilot/providers/copilot_providers.dart';
import 'package:operion_mobile/features/copilot/storage/copilot_conversation_cache.dart';

// ─────────────────────────────────────────────────────────────────────────────
// In-memory LocalDatabase fake.
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

class _FakeEndpoints extends CopilotEndpoints {
  _FakeEndpoints()
      : super(ApiClient.create(
          baseUrl: 'https://test.com',
          getAccessToken: () async => null,
        ));

  Map<String, dynamic> Function()? onListConversations;
  Map<String, dynamic> Function(String conversationId)? onGetConversation;

  @override
  Future<Map<String, dynamic>> listConversations({
    int limit = 20,
    String? cursor,
  }) async {
    return onListConversations?.call() ??
        <String, dynamic>{'items': <dynamic>[], 'next_cursor': null};
  }

  @override
  Future<Map<String, dynamic>> getConversation(String conversationId) async {
    return onGetConversation?.call(conversationId) ??
        <String, dynamic>{'conversation_id': conversationId, 'messages': <dynamic>[]};
  }
}

void main() {
  group('CopilotHistoryController', () {
    late _InMemoryLocalDatabase db;
    late _FakeEndpoints endpoints;
    late CopilotHistoryController controller;

    setUp(() {
      db = _InMemoryLocalDatabase();
      endpoints = _FakeEndpoints();
      controller = CopilotHistoryController(endpoints, CopilotConversationCache(db));
    });

    tearDown(() {
      controller.dispose();
    });

    test('loadConversations caches the fresh result as live data', () async {
      endpoints.onListConversations = () => <String, dynamic>{
            'items': <dynamic>[
              <String, dynamic>{'id': 'conv-1', 'title': 'First'},
            ],
            'next_cursor': null,
          };

      await controller.loadConversations();

      final state = controller.state;
      expect(state, isA<CopilotHistoryData>());
      final data = state as CopilotHistoryData;
      expect(data.isOffline, isFalse);
      expect(data.isReadOnly, isTrue);

      // The read-only snapshot must also be written to the offline cache,
      // flagged offline/read-only.
      final cached = await CopilotConversationCache(db).readCachedConversations();
      expect(cached, isNotNull);
      expect(cached!.isOffline, isTrue);
      expect(cached.isReadOnly, isTrue);
      expect((cached.data['items'] as List).single['id'], 'conv-1');
    });

    test('loadConversations falls back to the cache with an offline flag '
        'when the network fails', () async {
      // Seed the cache first.
      await CopilotConversationCache(db).cacheConversations(<String, dynamic>{
        'items': <dynamic>[
          <String, dynamic>{'id': 'conv-cached', 'title': 'Cached'},
        ],
        'next_cursor': null,
      });

      endpoints.onListConversations = () => throw Exception('offline');

      await controller.loadConversations();

      final state = controller.state;
      expect(state, isA<CopilotHistoryData>());
      final data = state as CopilotHistoryData;
      expect(data.isOffline, isTrue);
      expect(data.cachedAt, isNotNull);
      expect((data.data['items'] as List).single['id'], 'conv-cached');
    });

    test('loadConversations errors when the network fails and no cache exists',
        () async {
      endpoints.onListConversations = () => throw Exception('offline');

      await controller.loadConversations();

      expect(controller.state, isA<CopilotHistoryError>());
    });

    test('loadConversation caches the message history', () async {
      endpoints.onGetConversation = (id) => <String, dynamic>{
            'conversation_id': id,
            'messages': <dynamic>[
              <String, dynamic>{'role': 'user', 'content': 'hi'},
            ],
          };

      await controller.loadConversation('conv-1');

      final state = controller.state;
      expect(state, isA<CopilotHistoryData>());
      expect((state as CopilotHistoryData).isOffline, isFalse);

      final cached = await CopilotConversationCache(db).readCachedConversation('conv-1');
      expect(cached, isNotNull);
      expect(cached!.isOffline, isTrue);
      expect(cached.data['conversation_id'], 'conv-1');
    });

    test('loadConversation falls back to cached history when offline', () async {
      await CopilotConversationCache(db).cacheConversation(
        'conv-9',
        <String, dynamic>{
          'conversation_id': 'conv-9',
          'messages': <dynamic>[],
        },
      );

      endpoints.onGetConversation = (_) => throw Exception('offline');

      await controller.loadConversation('conv-9');

      final state = controller.state;
      expect(state, isA<CopilotHistoryData>());
      final data = state as CopilotHistoryData;
      expect(data.isOffline, isTrue);
      expect(data.cachedAt, isNotNull);
    });

    test('clearCache empties the cache and returns to loading', () async {
      await controller.loadConversations(); // writes the cache

      await controller.clearCache();

      expect(controller.state, isA<CopilotHistoryLoading>());
      expect(await CopilotConversationCache(db).readCachedConversations(), isNull);
    });
  });

  group('copilotHistoryProvider', () {
    test('resolves with overridden endpoints and local database', () async {
      final container = ProviderContainer(overrides: <Override>[
        copilotEndpointsProvider.overrideWithValue(_FakeEndpoints()),
        localDatabaseProvider.overrideWith((ref) => _InMemoryLocalDatabase()),
      ]);
      addTearDown(container.dispose);

      final controller = await container.read(copilotHistoryProvider.future);
      expect(controller, isA<CopilotHistoryController>());
      expect(controller.state, isA<CopilotHistoryLoading>());
    });
  });
}