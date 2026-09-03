/// Riverpod wiring for Co-Pilot push/in-app notifications (§32.5, §18, §23.1).
///
/// ## Activation
///
/// This provider is a side-effecting bridge: it must be read **once** during
/// app initialisation, after `pushServiceProvider` has been overridden with an
/// initialised [PushService]:
///
/// ```dart
/// ref.read(copilotNotificationBridgeProvider);
/// ```
///
/// ## What it wires
///
/// 1. **Backend pushes** — subscribes to [PushService.onNotification] and
///    surfaces `type: copilot_insight` / `type: copilot_circuit_breaker`
///    payloads in the in-app notification centre, matching how other modules
///    consume pushes.
/// 2. **Local state events** — listens to the Co-Pilot state machine and
///    raises the same notifications when an insight-ready completion or a
///    circuit-open error is produced locally.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/notifications/notification_providers.dart';
import '../providers/copilot_providers.dart';
import 'copilot_notification_service.dart';

/// Activates the bridge between Co-Pilot events and the notification layer.
final copilotNotificationBridgeProvider = Provider<CopilotNotificationService>(
  (ref) {
    final service = CopilotNotificationService(
      ref.watch(pushServiceProvider),
      ref.watch(inAppNotificationsProvider.notifier),
    );
    service.startListening();

    ref.listen<CopilotMobileState>(copilotStateProvider, (_, next) {
      if (next is CopilotCompleted &&
          next.summaryKey == CopilotEventKeys.insightReadySummaryKey) {
        service.addInsightReadyNotification({
          'summary_key': next.summaryKey,
          'params': next.params,
        });
      } else if (next is CopilotError &&
          next.messageKey == CopilotEventKeys.circuitOpenMessageKey) {
        service.addCircuitBreakerNotification({
          'message_key': next.messageKey,
        });
      }
    });

    ref.onDispose(service.dispose);
    return service;
  },
);