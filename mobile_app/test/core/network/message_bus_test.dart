import 'dart:async';

import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/network/message_bus.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/// A helper that collects events from a stream into a list.
StreamSubscription<BusEvent> _collect(
  Stream<BusEvent> stream,
  List<BusEvent> output,
) {
  return stream.listen(output.add);
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  group('MessageBus — publish / subscribe', () {
    late MessageBus bus;

    setUp(() {
      bus = MessageBus();
    });

    tearDown(() {
      bus.dispose();
    });

    // ── Basic emit / receive ─────────────────────

    test('single subscriber receives emitted event', () async {
      final events = <BusEvent>[];
      _collect(bus.stream, events);

      bus.emit(const ForceLogoutEvent());

      await Future(() {});
      expect(events, hasLength(1));
      expect(events.single, isA<ForceLogoutEvent>());
    });

    test('subscriber receives typed event with fields', () async {
      final events = <BusEvent>[];
      _collect(bus.stream, events);

      bus.emit(NewMessageEvent('thread-abc'));

      await Future(() {});
      expect(events, hasLength(1));
      final event = events.single as NewMessageEvent;
      expect(event.threadId, 'thread-abc');
    });

    test('subscriber receives StatusChangeEvent', () async {
      final events = <BusEvent>[];
      _collect(bus.stream, events);

      bus.emit(StatusChangeEvent('tr-100', 'delivered'));

      await Future(() {});
      expect(events, hasLength(1));
      final event = events.single as StatusChangeEvent;
      expect(event.transportId, 'tr-100');
      expect(event.newStatus, 'delivered');
    });

    test('subscriber receives FleetPositionEvent', () async {
      final events = <BusEvent>[];
      _collect(bus.stream, events);

      bus.emit(FleetPositionEvent('v-1', 45.5, 25.3));

      await Future(() {});
      expect(events, hasLength(1));
      final event = events.single as FleetPositionEvent;
      expect(event.vehicleId, 'v-1');
      expect(event.lat, 45.5);
      expect(event.lng, 25.3);
    });

    test('subscriber receives ConnectivityChangedEvent', () async {
      final events = <BusEvent>[];
      _collect(bus.stream, events);

      bus.emit(ConnectivityChangedEvent(false));

      await Future(() {});
      expect(events, hasLength(1));
      final event = events.single as ConnectivityChangedEvent;
      expect(event.isOnline, isFalse);
    });

    // ── Multiple subscribers ─────────────────────

    test('multiple subscribers receive the same event', () async {
      final events1 = <BusEvent>[];
      final events2 = <BusEvent>[];
      final sub1 = _collect(bus.stream, events1);
      final sub2 = _collect(bus.stream, events2);

      bus.emit(const ForceLogoutEvent());

      await Future(() {});
      expect(events1, hasLength(1));
      expect(events2, hasLength(1));
      expect(events1.single, isA<ForceLogoutEvent>());
      expect(events2.single, isA<ForceLogoutEvent>());

      await sub1.cancel();
      await sub2.cancel();
    });

    test('three subscribers all receive events', () async {
      final e1 = <BusEvent>[], e2 = <BusEvent>[], e3 = <BusEvent>[];
      final s1 = _collect(bus.stream, e1);
      final s2 = _collect(bus.stream, e2);
      final s3 = _collect(bus.stream, e3);

      bus.emit(NewMessageEvent('t1'));
      bus.emit(NewMessageEvent('t2'));

      await Future(() {});
      expect(e1, hasLength(2));
      expect(e2, hasLength(2));
      expect(e3, hasLength(2));

      await Future.wait([s1.cancel(), s2.cancel(), s3.cancel()]);
    });

    // ── Unsubscribe ──────────────────────────────

    test('unsubscribed listener stops receiving events', () async {
      final events = <BusEvent>[];
      final sub = _collect(bus.stream, events);

      bus.emit(const ForceLogoutEvent());
      await Future(() {});
      expect(events, hasLength(1));

      await sub.cancel();

      bus.emit(NewMessageEvent('after-cancel'));
      await Future(() {});
      expect(events, hasLength(1)); // still 1, not 2
    });

    test('cancelling subscription twice is safe', () async {
      final sub = bus.stream.listen((_) {});

      await sub.cancel();
      // Should not throw
      expect(() => sub.cancel(), returnsNormally);
    });

    test('unsubscribing mid-stream does not affect other listeners', () async {
      final events1 = <BusEvent>[];
      final events2 = <BusEvent>[];
      final sub1 = _collect(bus.stream, events1);
      final sub2 = _collect(bus.stream, events2);

      bus.emit(const ForceLogoutEvent());
      await Future(() {});
      expect(events1, hasLength(1));
      expect(events2, hasLength(1));

      await sub1.cancel();

      bus.emit(NewMessageEvent('only-for-2'));
      await Future(() {});
      expect(events1, hasLength(1)); // unchanged
      expect(events2, hasLength(2)); // received the new event
    });

    // ── Error resilience ─────────────────────────

    test('error in one subscriber does not crash the bus', () async {
      // Run in a zone that swallows errors from the throwing subscriber.
      await runZonedGuarded(() async {
        final events = <BusEvent>[];
        bus.stream.listen((_) => throw Exception('subscriber error'));
        bus.stream.listen(events.add);

        bus.emit(const ForceLogoutEvent());
        await Future(() {});

        expect(events, hasLength(1));
      }, (Object error, StackTrace stack) {
        // Expected – swallow.
      });
    });

    test('error in subscriber does not prevent future events', () async {
      await runZonedGuarded(() async {
        final events = <BusEvent>[];
        bus.stream.listen((_) => throw Exception('fail'));
        bus.stream.listen(events.add);

        bus.emit(const ForceLogoutEvent());
        await Future(() {});
        expect(events, hasLength(1));

        bus.emit(NewMessageEvent('second'));
        await Future(() {});
        expect(events, hasLength(2));
      }, (Object error, StackTrace stack) {
        // Expected – swallow.
      });
    });

    // ── Edge cases ───────────────────────────────

    test('emitting with no subscribers does nothing (no crash)', () {
      // No listeners attached
      expect(
        () => bus.emit(const ForceLogoutEvent()),
        returnsNormally,
      );
    });

    test('same subscriber registered twice receives events twice', () async {
      final events = <BusEvent>[];
      void handler(BusEvent e) => events.add(e);

      final sub1 = bus.stream.listen(handler);
      final sub2 = bus.stream.listen(handler);

      bus.emit(const ForceLogoutEvent());
      await Future(() {});

      expect(events, hasLength(2)); // called twice, once per subscription

      await sub1.cancel();
      await sub2.cancel();
    });

    test('can filter using where', () async {
      final newMessages = <NewMessageEvent>[];
      bus.stream
          .where((e) => e is NewMessageEvent)
          .cast<NewMessageEvent>()
          .listen(newMessages.add);

      bus.emit(const ForceLogoutEvent());
      bus.emit(NewMessageEvent('chat-1'));
      bus.emit(StatusChangeEvent('tr-1', 'loaded'));
      bus.emit(NewMessageEvent('chat-2'));

      await Future(() {});
      expect(newMessages, hasLength(2));
      expect(newMessages[0].threadId, 'chat-1');
      expect(newMessages[1].threadId, 'chat-2');
    });

    test('can filter using where on status changes', () async {
      final statusChanges = <StatusChangeEvent>[];
      bus.stream
          .where((e) => e is StatusChangeEvent)
          .cast<StatusChangeEvent>()
          .listen(statusChanges.add);

      bus.emit(NewMessageEvent('x'));
      bus.emit(StatusChangeEvent('tr-1', 'delivered'));

      await Future(() {});
      expect(statusChanges, hasLength(1));
    });

    // ── Dispose ──────────────────────────────────

    test('emit after dispose throws Exception', () {
      bus.dispose();

      expect(
        () => bus.emit(const ForceLogoutEvent()),
        throwsA(isA<Exception>()),
      );
    });

    test('emit after dispose does not crash the process', () {
      bus.dispose();
      expect(
        () => bus.emit(const ForceLogoutEvent()),
        throwsA(isA<Exception>()),
      );
    });

    test('dispose is idempotent', () {
      bus.dispose();
      // Calling dispose again should not throw
      expect(() => bus.dispose(), returnsNormally);
    });

    test('stream is a BroadcastStream', () {
      // Broadcast streams support multiple listeners
      expect(() {
        bus.stream.listen((_) {});
        bus.stream.listen((_) {});
      }, returnsNormally);
    });

    test('dispose closes underlying stream controller', () async {
      final events = <BusEvent>[];
      bus.stream.listen(events.add);

      bus.emit(const ForceLogoutEvent());
      await Future(() {});
      expect(events, hasLength(1));

      bus.dispose();

      // After dispose, no more events should be delivered (emit throws)
      expect(
        () => bus.emit(NewMessageEvent('after')),
        throwsA(isA<Exception>()),
      );
    });
  });
}
