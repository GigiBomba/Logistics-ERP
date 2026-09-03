import 'dart:async';

import 'package:dio/dio.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/copilot_endpoints.dart';
import 'package:operion_mobile/core/notifications/notification_providers.dart';
import 'package:operion_mobile/core/notifications/push_service.dart';
import 'package:operion_mobile/features/copilot/models/copilot_models.dart';
import 'package:operion_mobile/features/copilot/notifications/copilot_notification_providers.dart';
import 'package:operion_mobile/features/copilot/notifications/copilot_notification_service.dart';
import 'package:operion_mobile/features/copilot/providers/copilot_providers.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Minimal FirebaseMessaging stub (no Firebase platform channel needed).
// ─────────────────────────────────────────────────────────────────────────────

class StubFirebaseMessaging implements FirebaseMessaging {
  final _tokenRefreshController = StreamController<String>.broadcast();

  @override
  Stream<String> get onTokenRefresh => _tokenRefreshController.stream;

  void disposeService() => _tokenRefreshController.close();

  @override
  dynamic noSuchMethod(Invocation i) {
    if (i.isGetter) return null;
    if (i.isMethod) return Future.value();
    return null;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Fake endpoints for the state bridge tests.
// ─────────────────────────────────────────────────────────────────────────────

class _FakeEndpoints extends CopilotEndpoints {
  _FakeEndpoints()
      : super(ApiClient.create(
          baseUrl: 'https://test.com',
          getAccessToken: () async => null,
        ));

  CopilotResponse Function()? onChat;

  @override
  Future<CopilotResponse> chat({
    required String utterance,
    String? conversationId,
    String language = 'en',
    CancelToken? cancelToken,
  }) async {
    return onChat?.call() ?? const CopilotResponse(conversationId: 'conv');
  }
}

void main() {
  group('CopilotNotificationService', () {
    late StubFirebaseMessaging stubMessaging;
    late PushService pushService;
    late InAppNotificationNotifier notifier;
    late CopilotNotificationService service;

    setUp(() {
      stubMessaging = StubFirebaseMessaging();
      pushService = PushService(messaging: stubMessaging);
      notifier = InAppNotificationNotifier();
      service = CopilotNotificationService(pushService, notifier);
    });

    tearDown(() {
      service.dispose();
      pushService.dispose();
      stubMessaging.disposeService();
    });

    group('backend push subscription', () {
      test('surfaces a copilot_insight push as an in-app notification',
          () async {
        service.startListening();

        pushService.handleNotificationTap(const RemoteMessage(
          notification: null,
          data: <String, dynamic>{
            'type': 'copilot_insight',
            'summary': 'Fleet utilisation dropped below 40%.',
          },
        ));
        await Future<void>.delayed(Duration.zero);

        expect(notifier.state, hasLength(1));
        final notification = notifier.state.single;
        expect(notification.type, CopilotEventKeys.insightReadyType);
        expect(notification.title, 'Co-Pilot insight ready');
        expect(notification.body, contains('40%'));
      });

      test('surfaces a copilot_circuit_breaker push as an in-app notification',
          () async {
        service.startListening();

        pushService.handleNotificationTap(const RemoteMessage(
          notification: null,
          data: <String, dynamic>{'type': 'copilot_circuit_breaker'},
        ));
        await Future<void>.delayed(Duration.zero);

        expect(notifier.state, hasLength(1));
        final notification = notifier.state.single;
        expect(notification.type, CopilotEventKeys.circuitBreakerType);
        expect(notification.title, 'Co-Pilot temporarily paused');
      });

      test('ignores pushes unrelated to Co-Pilot', () async {
        service.startListening();

        pushService.handleNotificationTap(const RemoteMessage(
          notification: RemoteNotification(
            title: 'Status change',
            body: 'TR-42 delivered',
          ),
          data: <String, dynamic>{'type': 'status_change', 'transport_id': 'tr-42'},
        ));
        await Future<void>.delayed(Duration.zero);

        expect(notifier.state, isEmpty);
      });

      test('startListening is idempotent', () async {
        service.startListening();
        service.startListening();

        pushService.handleNotificationTap(const RemoteMessage(
          notification: null,
          data: <String, dynamic>{'type': 'copilot_insight'},
        ));
        await Future<void>.delayed(Duration.zero);

        expect(notifier.state, hasLength(1));
      });
    });

    group('local event methods', () {
      test('addInsightReadyNotification adds an insight notification', () {
        service.addInsightReadyNotification(<String, dynamic>{
          'summary': 'New insight',
        });

        expect(notifier.state, hasLength(1));
        expect(notifier.state.single.type, CopilotEventKeys.insightReadyType);
        expect(notifier.state.single.body, 'New insight');
      });

      test('addCircuitBreakerNotification adds a circuit notification', () {
        service.addCircuitBreakerNotification(<String, dynamic>{
          'message': 'circuit open',
        });

        expect(notifier.state, hasLength(1));
        expect(
          notifier.state.single.type,
          CopilotEventKeys.circuitBreakerType,
        );
        expect(notifier.state.single.body, 'circuit open');
      });

      test('ids are unique across events', () {
        service.addInsightReadyNotification(const <String, dynamic>{});
        service.addCircuitBreakerNotification(const <String, dynamic>{});
        service.addInsightReadyNotification(const <String, dynamic>{});

        final ids = notifier.state.map((n) => n.id).toSet();
        expect(ids, hasLength(3));
      });
    });
  });

  group('copilotNotificationBridgeProvider', () {
    test('fires an insight-ready notification on insight summary completion',
        () async {
      final push = PushService(messaging: StubFirebaseMessaging());
      final fakeEndpoints = _FakeEndpoints()
        ..onChat = () => const CopilotResponse(
              conversationId: 'conv-1',
              summaryKey: CopilotEventKeys.insightReadySummaryKey,
            );

      final container = ProviderContainer(overrides: <Override>[
        pushServiceProvider.overrideWithValue(push),
        copilotEndpointsProvider.overrideWithValue(fakeEndpoints),
      ]);
      addTearDown(container.dispose);
      addTearDown(push.dispose);

      // Activate the bridge.
      container.read(copilotNotificationBridgeProvider);

      await container.read(copilotStateProvider.notifier).sendMessage('summarize');
      await Future<void>.delayed(Duration.zero);

      final notifications = container.read(inAppNotificationsProvider);
      expect(notifications, hasLength(1));
      expect(notifications.single.type, CopilotEventKeys.insightReadyType);
    });

    test('fires a circuit-breaker notification on a 503 error', () async {
      final push = PushService(messaging: StubFirebaseMessaging());
      final fakeEndpoints = _FakeEndpoints()
        ..onChat = () => throw DioException.badResponse(
              statusCode: 503,
              requestOptions: RequestOptions(path: '/api/v1/copilot/chat'),
              response: Response(
                requestOptions: RequestOptions(path: '/api/v1/copilot/chat'),
                statusCode: 503,
              ),
            );

      final container = ProviderContainer(overrides: <Override>[
        pushServiceProvider.overrideWithValue(push),
        copilotEndpointsProvider.overrideWithValue(fakeEndpoints),
      ]);
      addTearDown(container.dispose);
      addTearDown(push.dispose);

      container.read(copilotNotificationBridgeProvider);

      await container.read(copilotStateProvider.notifier).sendMessage('dispatch');
      await Future<void>.delayed(Duration.zero);

      final notifications = container.read(inAppNotificationsProvider);
      expect(notifications, hasLength(1));
      expect(notifications.single.type, CopilotEventKeys.circuitBreakerType);
    });

    test('surfaces a backend copilot_insight push', () async {
      final push = PushService(messaging: StubFirebaseMessaging());
      final container = ProviderContainer(overrides: <Override>[
        pushServiceProvider.overrideWithValue(push),
        copilotEndpointsProvider.overrideWithValue(_FakeEndpoints()),
      ]);
      addTearDown(container.dispose);
      addTearDown(push.dispose);

      container.read(copilotNotificationBridgeProvider);

      push.handleNotificationTap(const RemoteMessage(
        notification: null,
        data: <String, dynamic>{'type': 'copilot_insight', 'summary': 'x'},
      ));
      await Future<void>.delayed(Duration.zero);

      final notifications = container.read(inAppNotificationsProvider);
      expect(notifications, hasLength(1));
      expect(notifications.single.type, CopilotEventKeys.insightReadyType);
    });
  });
}