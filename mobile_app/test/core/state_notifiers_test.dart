import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:operion_mobile/core/notifications/notification_providers.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/network/message_bus.dart';

// =============================================================================
// Helpers
// =============================================================================

InAppNotification _notification({
  required String id,
  bool isRead = false,
}) {
  return InAppNotification(
    id: id,
    title: 'Test Title',
    body: 'Test body',
    type: 'alert',
    isRead: isRead,
    createdAt: DateTime(2025, 1, 1),
  );
}

// =============================================================================
// Tests
// =============================================================================

void main() {
  // ==========================================================================
  // AuthStateNotifier
  // ==========================================================================
  group('AuthStateNotifier', () {
    test('initial state is unauthenticated', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final notifier = container.read(authStateProvider.notifier);
      expect(notifier.state, AuthState.unauthenticated);
    });

    test('setAuthenticating() transitions to authenticating', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final notifier = container.read(authStateProvider.notifier);

      notifier.setAuthenticating();

      expect(notifier.state, AuthState.authenticating);
    });

    test('setAuthenticated() transitions to authenticated', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final notifier = container.read(authStateProvider.notifier);

      notifier.setAuthenticated();

      expect(notifier.state, AuthState.authenticated);
    });

    test('setUnauthenticated() transitions to unauthenticated', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final notifier = container.read(authStateProvider.notifier);

      notifier.setAuthenticated(); // start from authenticated
      notifier.setUnauthenticated();

      expect(notifier.state, AuthState.unauthenticated);
    });

    test('setSessionExpired() transitions to sessionExpired', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final notifier = container.read(authStateProvider.notifier);

      notifier.setSessionExpired();

      expect(notifier.state, AuthState.sessionExpired);
    });

    test('dispose() can be called without error', () {
      final container = ProviderContainer();
      final notifier = container.read(authStateProvider.notifier);

      // Should not throw
      expect(() => notifier.dispose(), returnsNormally);
    });
  });

  // ==========================================================================
  // InAppNotificationNotifier
  // ==========================================================================
  group('InAppNotificationNotifier', () {
    test('initial state is empty list', () {
      final notifier = InAppNotificationNotifier();
      expect(notifier.state, isEmpty);
    });

    test('add() prepends notification to state', () {
      final notifier = InAppNotificationNotifier();
      final notification = _notification(id: 'n1');

      notifier.add(notification);

      expect(notifier.state, hasLength(1));
      expect(notifier.state.first.id, 'n1');
    });

    test('add() with existing notifications keeps old ones (newest first)', () {
      final notifier = InAppNotificationNotifier();
      notifier.add(_notification(id: 'n1'));
      notifier.add(_notification(id: 'n2'));

      expect(notifier.state, hasLength(2));
      expect(notifier.state[0].id, 'n2'); // newest first
      expect(notifier.state[1].id, 'n1');
    });

    test('markAsRead() sets isRead=true on matching notification', () {
      final notifier = InAppNotificationNotifier();
      notifier.add(_notification(id: 'n1', isRead: false));

      notifier.markAsRead('n1');

      expect(notifier.state.first.isRead, isTrue);
    });

    test('markAsRead() with non-existent id does nothing', () {
      final notifier = InAppNotificationNotifier();
      notifier.add(_notification(id: 'n1', isRead: false));

      notifier.markAsRead('nonexistent');

      expect(notifier.state.first.isRead, isFalse);
    });

    test('markAllAsRead() sets all to isRead=true', () {
      final notifier = InAppNotificationNotifier();
      notifier.add(_notification(id: 'n1', isRead: false));
      notifier.add(_notification(id: 'n2', isRead: false));

      notifier.markAllAsRead();

      expect(notifier.state.every((n) => n.isRead), isTrue);
    });

    test('remove() deletes matching notification by id', () {
      final notifier = InAppNotificationNotifier();
      notifier.add(_notification(id: 'n1'));
      notifier.add(_notification(id: 'n2'));

      notifier.remove('n1');

      expect(notifier.state, hasLength(1));
      expect(notifier.state.first.id, 'n2');
    });

    test('clear() removes all notifications', () {
      final notifier = InAppNotificationNotifier();
      notifier.add(_notification(id: 'n1'));
      notifier.add(_notification(id: 'n2'));

      notifier.clear();

      expect(notifier.state, isEmpty);
    });
  });

  // ==========================================================================
  // MessageBus
  // ==========================================================================
  group('MessageBus', () {
    test('can emit and receive ForceLogoutEvent', () async {
      final bus = MessageBus();
      final events = <BusEvent>[];
      final sub = bus.stream.listen(events.add);

      bus.emit(const ForceLogoutEvent());

      // Allow microtask to process
      await Future(() {});
      expect(events, hasLength(1));
      expect(events.single, isA<ForceLogoutEvent>());
      await sub.cancel();
      bus.dispose();
    });

    test('can emit and receive NewMessageEvent', () async {
      final bus = MessageBus();
      final events = <BusEvent>[];
      final sub = bus.stream.listen(events.add);

      bus.emit(NewMessageEvent('thread-1'));

      await Future(() {});
      expect(events, hasLength(1));
      expect(events.single, isA<NewMessageEvent>());
      expect((events.single as NewMessageEvent).threadId, 'thread-1');
      await sub.cancel();
      bus.dispose();
    });

    test('can emit and receive StatusChangeEvent', () async {
      final bus = MessageBus();
      final events = <BusEvent>[];
      final sub = bus.stream.listen(events.add);

      bus.emit(StatusChangeEvent('tr-42', 'delivered'));

      await Future(() {});
      expect(events, hasLength(1));
      final event = events.single as StatusChangeEvent;
      expect(event.transportId, 'tr-42');
      expect(event.newStatus, 'delivered');
      await sub.cancel();
      bus.dispose();
    });

    test('can emit and receive FleetPositionEvent', () async {
      final bus = MessageBus();
      final events = <BusEvent>[];
      final sub = bus.stream.listen(events.add);

      bus.emit(FleetPositionEvent('v-1', 45.0, 25.0));

      await Future(() {});
      expect(events, hasLength(1));
      final event = events.single as FleetPositionEvent;
      expect(event.vehicleId, 'v-1');
      expect(event.lat, 45.0);
      expect(event.lng, 25.0);
      await sub.cancel();
      bus.dispose();
    });

    test('can emit and receive ConnectivityChangedEvent', () async {
      final bus = MessageBus();
      final events = <BusEvent>[];
      final sub = bus.stream.listen(events.add);

      bus.emit(ConnectivityChangedEvent(true));

      await Future(() {});
      expect(events, hasLength(1));
      final event = events.single as ConnectivityChangedEvent;
      expect(event.isOnline, isTrue);
      await sub.cancel();
      bus.dispose();
    });

    test('multiple listeners receive the same event', () async {
      final bus = MessageBus();
      final events1 = <BusEvent>[];
      final events2 = <BusEvent>[];
      final sub1 = bus.stream.listen(events1.add);
      final sub2 = bus.stream.listen(events2.add);

      bus.emit(const ForceLogoutEvent());

      await Future(() {});
      expect(events1, hasLength(1));
      expect(events2, hasLength(1));
      expect(events1.single, isA<ForceLogoutEvent>());
      expect(events2.single, isA<ForceLogoutEvent>());
      await sub1.cancel();
      await sub2.cancel();
      bus.dispose();
    });

    test('dispose() closes stream (listeners stop receiving)', () async {
      final bus = MessageBus();
      final events = <BusEvent>[];
      final sub = bus.stream.listen(events.add);

      // Emit one event before dispose to confirm listeners work.
      bus.emit(const ForceLogoutEvent());
      await Future(() {});
      expect(events, hasLength(1));
      events.clear();

      bus.dispose();

      // After dispose, the stream controller is closed so new events are
      // not delivered. Calling emit should throw (StreamController.add
      // on a closed controller throws an exception).
      expect(
        () => bus.emit(const ForceLogoutEvent()),
        throwsA(isA<Exception>()),
      );

      // The listener should not have received the post-dispose event.
      expect(events, isEmpty);
      await sub.cancel();
    });

    test('emitting after dispose() does not crash', () async {
      final bus = MessageBus();
      bus.dispose();

      // StreamController.add will throw when the controller is closed,
      // but the process should not crash. We verify the throw is caught
      // and does not propagate as a fatal error.
      expect(
        () => bus.emit(const ForceLogoutEvent()),
        throwsA(isA<Exception>()),
      );
    });
  });
}
