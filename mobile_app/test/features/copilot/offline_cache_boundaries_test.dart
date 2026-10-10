import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/copilot_endpoints.dart';
import 'package:operion_mobile/core/storage/local_db.dart';
import 'package:operion_mobile/core/sync/connectivity_monitor.dart';
import 'package:operion_mobile/features/copilot/models/copilot_models.dart';
import 'package:operion_mobile/features/copilot/notifications/copilot_notification_service.dart';
import 'package:operion_mobile/features/copilot/providers/copilot_providers.dart';
import 'package:operion_mobile/features/copilot/storage/copilot_conversation_cache.dart';
import 'package:operion_mobile/l10n/app_localizations.dart';

// ── In-memory LocalDatabase fake (§32.3 cache tests) ───────────────────────

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

// ── Recording fake endpoints ───────────────────────────────────────────────

/// Fakes every Co-Pilot endpoint while counting how many times each call was
/// made, so offline-gate tests can prove no request is issued.
class _RecordingCopilotEndpoints extends CopilotEndpoints {
  _RecordingCopilotEndpoints()
      : super(ApiClient.create(
          baseUrl: 'https://test.com',
          getAccessToken: () async => null,
        ));

  int chatCalls = 0;
  int confirmCalls = 0;
  int cancelCalls = 0;
  int listConversationsCalls = 0;
  int getConversationCalls = 0;

  CopilotResponse Function()? onChat;
  Map<String, dynamic> Function()? onConfirmPlan;
  Map<String, dynamic> Function()? onCancelPlan;
  Map<String, dynamic> Function()? onListConversations;
  Map<String, dynamic> Function(String conversationId)? onGetConversation;

  @override
  Future<CopilotResponse> chat({
    required String utterance,
    String? conversationId,
    String language = 'en',
    CancelToken? cancelToken,
  }) async {
    chatCalls++;
    return onChat?.call() ??
        CopilotResponse(conversationId: 'test-conv');
  }

  @override
  Future<Map<String, dynamic>> confirmPlan(
    String planId,
    CancelToken? cancelToken, {
    String? confirmationPhrase,
  }) async {
    confirmCalls++;
    return onConfirmPlan?.call() ?? {'status': 'completed'};
  }

  @override
  Future<Map<String, dynamic>> cancelPlan(String planId) async {
    cancelCalls++;
    return onCancelPlan?.call() ?? {'status': 'cancelled'};
  }

  @override
  Future<Map<String, dynamic>> listConversations({
    int limit = 20,
    String? cursor,
  }) async {
    listConversationsCalls++;
    return onListConversations?.call() ??
        <String, dynamic>{'items': <dynamic>[], 'next_cursor': null};
  }

  @override
  Future<Map<String, dynamic>> getConversation(
    String conversationId,
  ) async {
    getConversationCalls++;
    return onGetConversation?.call(conversationId) ??
        <String, dynamic>{
          'conversation_id': conversationId,
          'messages': <dynamic>[],
        };
  }
}

// ── Connectivity fakes (Riverpod wiring) ───────────────────────────────────

class _NoopConnectivity implements Connectivity {
  @override
  Future<List<ConnectivityResult>> checkConnectivity() async =>
      const [ConnectivityResult.wifi];

  @override
  Stream<List<ConnectivityResult>> get onConnectivityChanged =>
      const Stream.empty();
}

class _FakeConnectivityMonitor extends ConnectivityMonitor {
  _FakeConnectivityMonitor({required bool online})
      : _online = online,
        super(connectivity: _NoopConnectivity());

  bool _online;

  @override
  bool get isOnline => _online;

  set online(bool value) => _online = value;
}

// ── Plan helpers ───────────────────────────────────────────────────────────

CopilotExecutionPlan _planWithConfirmationLevels({
  List<int> levels = const [],
  bool requiresConfirmation = true,
  String? confirmationPhrase,
}) {
  return CopilotExecutionPlan(
    planId: 'plan-test',
    conversationId: 'conv-test',
    intent: const CopilotIntent(name: 'vehicle.search', rawUtterance: 'test'),
    requiresConfirmation: requiresConfirmation,
    confirmationPhrase: confirmationPhrase,
    steps: levels.asMap().entries.map((e) => CopilotExecutionStep(
          stepId: 's${e.key}',
          toolName: 'vehicle.search',
          confirmationLevel: e.value,
          status: 'pending',
        )).toList(),
  );
}

void main() {
  group('test_offline_cache_boundaries (§32.3)', () {
    late _InMemoryLocalDatabase db;
    late _RecordingCopilotEndpoints endpoints;

    setUp(() {
      db = _InMemoryLocalDatabase();
      endpoints = _RecordingCopilotEndpoints();
    });

    // ======================================================================
    // (a) Cached conversation history is readable offline
    // ======================================================================
    group('cached conversation history is readable offline', () {
      test('loadConversation serves cached message history with offline flag '
          'when the network request fails', () async {
        await CopilotConversationCache(db).cacheConversation(
          'conv-offline',
          <String, dynamic>{
            'conversation_id': 'conv-offline',
            'messages': <dynamic>[
              <String, dynamic>{'role': 'user', 'content': 'cached hello'},
            ],
          },
        );

        // The endpoint is unreachable while offline.
        endpoints.onGetConversation = (_) => throw Exception('offline');

        final controller = CopilotHistoryController(
          endpoints,
          CopilotConversationCache(db),
        );
        addTearDown(controller.dispose);

        await controller.loadConversation('conv-offline');

        final state = controller.state;
        expect(state, isA<CopilotHistoryData>());
        final data = state as CopilotHistoryData;
        expect(data.isOffline, isTrue);
        expect(data.isReadOnly, isTrue);
        expect(data.cachedAt, isNotNull);
        expect(data.data['conversation_id'], 'conv-offline');
        expect(
          (data.data['messages'] as List).single['content'],
          'cached hello',
        );
      });

      test('loadConversations serves the cached conversation list with '
          'offline flag when the network request fails', () async {
        await CopilotConversationCache(db).cacheConversations(<String, dynamic>{
          'items': <dynamic>[
            <String, dynamic>{'id': 'conv-cached', 'title': 'Cached'},
          ],
          'next_cursor': null,
        });

        endpoints.onListConversations = () => throw Exception('offline');

        final controller = CopilotHistoryController(
          endpoints,
          CopilotConversationCache(db),
        );
        addTearDown(controller.dispose);

        await controller.loadConversations();

        final state = controller.state;
        expect(state, isA<CopilotHistoryData>());
        final data = state as CopilotHistoryData;
        expect(data.isOffline, isTrue);
        expect(data.cachedAt, isNotNull);
        expect((data.data['items'] as List).single['id'], 'conv-cached');
      });
    });

    // ======================================================================
    // (b) Offline confirm of a Level 2+ plan is blocked with a clear message
    // ======================================================================
    group('offline confirm gate blocks Level 2+ plans', () {
      test('Level 2 plan: confirm while offline → CopilotError with the '
          'offline message key and zero endpoint calls', () async {
        final plan = _planWithConfirmationLevels(levels: [2]);
        final notifier = CopilotStateNotifier(
          endpoints,
          isOnline: () => false,
        )..state = CopilotAwaitingConfirmation(plan: plan);
        addTearDown(notifier.dispose);
        endpoints.onConfirmPlan = () => {'status': 'completed'};

        await notifier.confirmPlan();

        expect(notifier.state, isA<CopilotError>());
        expect(
          (notifier.state as CopilotError).messageKey,
          CopilotEventKeys.offlineConfirmMessageKey,
        );
        // The request must never be fired while offline.
        expect(endpoints.confirmCalls, 0);
      });

      test('Level 3 plan with phrase: confirm while offline → CopilotError '
          'with the offline message key and zero endpoint calls', () async {
        final plan = _planWithConfirmationLevels(
          levels: [3],
          confirmationPhrase: 'I understand the risks',
        );
        final notifier = CopilotStateNotifier(
          endpoints,
          isOnline: () => false,
        )..state = CopilotAwaitingConfirmation(plan: plan);
        addTearDown(notifier.dispose);
        endpoints.onConfirmPlan = () => {'status': 'completed'};

        await notifier.confirmPlan(confirmationPhrase: 'I understand the risks');

        expect(notifier.state, isA<CopilotError>());
        expect(
          (notifier.state as CopilotError).messageKey,
          CopilotEventKeys.offlineConfirmMessageKey,
        );
        expect(endpoints.confirmCalls, 0);
      });

      test('offline message key resolves to a clear localized message (l10n)',
          () {
        final l10n = AppLocalizations(const Locale('en'));
        expect(
          CopilotEventKeys.offlineConfirmMessageKey,
          'copilot.confirm.offline_required',
        );
        // The user-facing string is a real message, not the raw key.
        expect(l10n.copilot_confirm_offline_required, contains('offline'));
      });

      test('connectionError during confirm maps to the offline message key',
          () async {
        final plan = _planWithConfirmationLevels(levels: [2]);
        final notifier = CopilotStateNotifier(
          endpoints,
          isOnline: () => true,
        )..state = CopilotAwaitingConfirmation(plan: plan);
        addTearDown(notifier.dispose);
        // Connectivity probe looked online but the request never reached the
        // server (Dio connectionError) — same reconnect message surfaces.
        endpoints.onConfirmPlan = () => throw DioException(
              requestOptions: RequestOptions(
                path: '/api/v1/copilot/plans/plan-test/confirm',
              ),
              type: DioExceptionType.connectionError,
            );

        await notifier.confirmPlan();

        expect(endpoints.confirmCalls, 1);
        expect(notifier.state, isA<CopilotError>());
        expect(
          (notifier.state as CopilotError).messageKey,
          CopilotEventKeys.offlineConfirmMessageKey,
        );
      });
    });

    // ======================================================================
    // (c) Online confirm still works
    // ======================================================================
    group('online confirm still works', () {
      test('Level 2 plan: confirm while online reaches the endpoint and '
          'completes', () async {
        final plan = _planWithConfirmationLevels(levels: [2]);
        final notifier = CopilotStateNotifier(
          endpoints,
          isOnline: () => true,
        )..state = CopilotAwaitingConfirmation(plan: plan);
        addTearDown(notifier.dispose);
        endpoints.onConfirmPlan = () => {'status': 'completed'};

        await notifier.confirmPlan();

        // The request reached the endpoint exactly once.
        expect(endpoints.confirmCalls, 1);
        expect(notifier.state, isA<CopilotCompleted>());
        expect(
          (notifier.state as CopilotCompleted).summaryKey,
          'copilot.summary.confirmed',
        );
      });

      test('Level 3 plan with phrase: confirm while online reaches the '
          'endpoint and completes', () async {
        final plan = _planWithConfirmationLevels(
          levels: [3],
          confirmationPhrase: 'I understand the risks',
        );
        final notifier = CopilotStateNotifier(
          endpoints,
          isOnline: () => true,
        )..state = CopilotAwaitingConfirmation(plan: plan);
        addTearDown(notifier.dispose);
        endpoints.onConfirmPlan = () => {'status': 'completed'};

        await notifier.confirmPlan(confirmationPhrase: 'I understand the risks');

        expect(endpoints.confirmCalls, 1);
        expect(notifier.state, isA<CopilotCompleted>());
      });
    });

    // ======================================================================
    // Riverpod container wiring: copilotStateProvider reads connectivity
    // ======================================================================
    group('copilotStateProvider wiring (Riverpod container)', () {
      test('confirm while offline is blocked through the wired provider',
          () async {
        final monitor = _FakeConnectivityMonitor(online: false);
        final container = ProviderContainer(overrides: <Override>[
          copilotEndpointsProvider.overrideWithValue(endpoints),
          connectivityProvider.overrideWithValue(monitor),
        ]);
        addTearDown(container.dispose);

        final notifier = container.read(copilotStateProvider.notifier);

        // Drive the notifier into CopilotAwaitingConfirmation via chat.
        final plan = _planWithConfirmationLevels(levels: [2]);
        endpoints.onChat = () =>
            CopilotResponse(conversationId: 'conv-1', plan: plan);
        await notifier.sendMessage('confirm dispatch');
        expect(notifier.state, isA<CopilotAwaitingConfirmation>());

        endpoints.onConfirmPlan = () => {'status': 'completed'};
        await notifier.confirmPlan();

        expect(notifier.state, isA<CopilotError>());
        expect(
          (notifier.state as CopilotError).messageKey,
          CopilotEventKeys.offlineConfirmMessageKey,
        );
        expect(endpoints.confirmCalls, 0);
      });

      test('confirm while online proceeds through the wired provider',
          () async {
        final monitor = _FakeConnectivityMonitor(online: true);
        final container = ProviderContainer(overrides: <Override>[
          copilotEndpointsProvider.overrideWithValue(endpoints),
          connectivityProvider.overrideWithValue(monitor),
        ]);
        addTearDown(container.dispose);

        final notifier = container.read(copilotStateProvider.notifier);

        final plan = _planWithConfirmationLevels(levels: [2]);
        endpoints.onChat = () =>
            CopilotResponse(conversationId: 'conv-1', plan: plan);
        await notifier.sendMessage('confirm dispatch');

        endpoints.onConfirmPlan = () => {'status': 'completed'};
        await notifier.confirmPlan();

        expect(endpoints.confirmCalls, 1);
        expect(notifier.state, isA<CopilotCompleted>());
      });
    });
  });
}