/// Bridges Co-Pilot events into the push / in-app notification layer.
///
/// Two sources are wired, mirroring how the rest of the app consumes pushes
/// (foreground FCM messages surfaced through the in-app notification centre):
///
/// 1. **Backend pushes** — the backend's AlertManager / notification infra
///    sends FCM messages whose `data.type` is `copilot_insight` (§18) or
///    `copilot_circuit_breaker` (§23.1). [CopilotNotificationService] listens
///    to [PushService.onNotification] and surfaces those payloads through
///    [InAppNotificationNotifier].
/// 2. **Local state events** — the same notifications can be raised from the
///    mobile Co-Pilot state machine via [addInsightReadyNotification] /
///    [addCircuitBreakerNotification]; the Riverpod bridge in
///    `copilot_notification_providers.dart` does this automatically.
library;

import 'dart:async';
import 'dart:developer' as developer;

import '../../../core/notifications/notification_providers.dart';
import '../../../core/notifications/push_service.dart';

/// Well-known keys for Co-Pilot notification events (§18, §23.1).
abstract final class CopilotEventKeys {
  /// FCM push `data['type']` for "insight ready" (§18).
  static const String insightReadyType = 'copilot_insight';

  /// FCM push `data['type']` for circuit-breaker trips (§23.1).
  static const String circuitBreakerType = 'copilot_circuit_breaker';

  /// Local `message_key` surfaced when the backend reports an open circuit
  /// breaker (mapped from HTTP 503 in `CopilotStateNotifier`).
  static const String circuitOpenMessageKey = 'copilot.error.circuit_open';

  /// Local `message_key` surfaced when the user tries to confirm a Level 2+
  /// plan while offline (§32.3) — the request is never fired and the user is
  /// told to reconnect to confirm.
  static const String offlineConfirmMessageKey =
      'copilot.confirm.offline_required';

  /// Local `summary_key` convention for a chat turn that completes an insight.
  static const String insightReadySummaryKey = 'copilot.summary.insight_ready';
}

/// Forwards Co-Pilot events to the in-app notification centre.
class CopilotNotificationService {
  final PushService _pushService;
  final InAppNotificationNotifier _notifier;
  StreamSubscription<PushNotification>? _pushSubscription;
  int _seq = 0;

  CopilotNotificationService(this._pushService, this._notifier);

  /// Starts forwarding Co-Pilot typed pushes into the notification centre.
  ///
  /// Safe to call more than once — a duplicate subscription is never created.
  void startListening() {
    if (_pushSubscription != null) return;
    _pushSubscription = _pushService.onNotification.listen(_handlePush);
    developer.log(
      'CopilotNotificationService: listening for copilot pushes',
      name: 'CopilotNotificationService',
    );
  }

  /// Surfaces an "insight ready" event as an in-app notification (§18).
  void addInsightReadyNotification(Map<String, dynamic> data) {
    final title =
        data['title']?.toString() ?? 'Co-Pilot insight ready';
    final body = data['summary']?.toString() ??
        data['body']?.toString() ??
        'A new proactive insight is ready for review.';
    _notifier.add(InAppNotification(
      id: 'copilot-insight-${_nextId()}',
      title: title,
      body: body,
      type: CopilotEventKeys.insightReadyType,
      createdAt: DateTime.now(),
    ));
  }

  /// Surfaces a circuit-breaker trip as an in-app notification (§23.1).
  void addCircuitBreakerNotification(Map<String, dynamic> data) {
    final title = data['title']?.toString() ?? 'Co-Pilot temporarily paused';
    final body = data['message']?.toString() ??
        data['body']?.toString() ??
        'The AI assistant is temporarily unavailable. Please retry shortly.';
    _notifier.add(InAppNotification(
      id: 'copilot-circuit-${_nextId()}',
      title: title,
      body: body,
      type: CopilotEventKeys.circuitBreakerType,
      createdAt: DateTime.now(),
    ));
  }

  /// Stops listening and releases resources.
  void dispose() {
    _pushSubscription?.cancel();
    _pushSubscription = null;
  }

  void _handlePush(PushNotification notification) {
    final type = notification.data['type'] as String?;
    if (type == CopilotEventKeys.insightReadyType) {
      addInsightReadyNotification(notification.data);
    } else if (type == CopilotEventKeys.circuitBreakerType) {
      addCircuitBreakerNotification(notification.data);
    }
  }

  int _nextId() => ++_seq;
}