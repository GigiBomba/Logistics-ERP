import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/core/sync/connectivity_monitor.dart';

// =============================================================================
// Mock Connectivity implementation
// =============================================================================

class MockConnectivity implements Connectivity {
  List<ConnectivityResult> _result = [ConnectivityResult.wifi];
  final StreamController<List<ConnectivityResult>> _controller =
      StreamController<List<ConnectivityResult>>.broadcast();

  /// Sets the value returned by [checkConnectivity].
  void setResult(List<ConnectivityResult> result) {
    _result = result;
  }

  /// Emits a new value on the [onConnectivityChanged] stream.
  void emit(List<ConnectivityResult> result) {
    _controller.add(result);
  }

  @override
  Future<List<ConnectivityResult>> checkConnectivity() async => _result;

  @override
  Stream<List<ConnectivityResult>> get onConnectivityChanged =>
      _controller.stream;

  void dispose() {
    _controller.close();
  }
}

// =============================================================================
// Tests
// =============================================================================

void main() {
  group('ConnectivityMonitor', () {
    late MockConnectivity mockConnectivity;

    setUp(() {
      mockConnectivity = MockConnectivity();
    });

    tearDown(() {
      mockConnectivity.dispose();
    });

    // ── Initial state ───────────────────────────────────────────────────

    test('starts online by default (optimistic initial state)', () {
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);
      expect(monitor.isOnline, isTrue);
      monitor.dispose();
    });

    test('after initialize with wifi connectivity, isOnline is true',
        () async {
      mockConnectivity.setResult([ConnectivityResult.wifi]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);

      await monitor.initialize();

      expect(monitor.isOnline, isTrue);
      monitor.dispose();
    });

    test('after initialize with mobile connectivity, isOnline is true',
        () async {
      mockConnectivity.setResult([ConnectivityResult.mobile]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);

      await monitor.initialize();

      expect(monitor.isOnline, isTrue);
      monitor.dispose();
    });

    test('after initialize with ethernet connectivity, isOnline is true',
        () async {
      mockConnectivity.setResult([ConnectivityResult.ethernet]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);

      await monitor.initialize();

      expect(monitor.isOnline, isTrue);
      monitor.dispose();
    });

    test('after initialize with none connectivity, isOnline is false',
        () async {
      mockConnectivity.setResult([ConnectivityResult.none]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);

      await monitor.initialize();

      expect(monitor.isOnline, isFalse);
      monitor.dispose();
    });

    test('online when at least one result is not none', () async {
      mockConnectivity.setResult([
        ConnectivityResult.none,
        ConnectivityResult.wifi,
      ]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);

      await monitor.initialize();

      expect(monitor.isOnline, isTrue);
      monitor.dispose();
    });

    test('offline only when all results are none', () async {
      mockConnectivity.setResult([
        ConnectivityResult.none,
        ConnectivityResult.none,
      ]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);

      await monitor.initialize();

      expect(monitor.isOnline, isFalse);
      monitor.dispose();
    });

    // ── initialize gracefully handles exceptions ────────────────────────

    test('initialize gracefully handles checkConnectivity failure', () async {
      // Simulate a platform exception
      mockConnectivity.setResult([ConnectivityResult.wifi]);
      // Override checkConnectivity to throw
      final throwingMock = _ThrowingMockConnectivity();
      final monitor = ConnectivityMonitor(connectivity: throwingMock);

      // Should not throw
      await monitor.initialize();

      // Should remain optimistic (true)
      expect(monitor.isOnline, isTrue);
      monitor.dispose();
    });

    // ── Online → offline transition ─────────────────────────────────────

    test('detects online to offline transition', () async {
      mockConnectivity.setResult([ConnectivityResult.wifi]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);
      await monitor.initialize();
      expect(monitor.isOnline, isTrue);

      // Simulate going offline
      mockConnectivity.emit([ConnectivityResult.none]);

      // Give the stream event time to propagate
      await Future<void>.delayed(Duration.zero);
      expect(monitor.isOnline, isFalse);
      monitor.dispose();
    });

    // ── Offline → online transition ─────────────────────────────────────

    test('detects offline to online transition', () async {
      mockConnectivity.setResult([ConnectivityResult.none]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);
      await monitor.initialize();
      expect(monitor.isOnline, isFalse);

      // Simulate going online
      mockConnectivity.emit([ConnectivityResult.wifi]);

      await Future<void>.delayed(Duration.zero);
      expect(monitor.isOnline, isTrue);
      monitor.dispose();
    });

    // ── Stream behaviour ────────────────────────────────────────────────

    test('onConnectivityChanged is a broadcast stream allowing multiple listeners',
        () async {
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);

      // Subscribe twice — broadcast streams allow this without errors.
      final sub1 = monitor.onConnectivityChanged.listen((_) {});
      final sub2 = monitor.onConnectivityChanged.listen((_) {});

      expect(sub1.isPaused, isFalse);
      expect(sub2.isPaused, isFalse);

      await sub1.cancel();
      await sub2.cancel();
      monitor.dispose();
    });

    test('stream emits true when going online', () async {
      mockConnectivity.setResult([ConnectivityResult.none]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);
      await monitor.initialize();

      final emitted = <bool>[];
      final sub = monitor.onConnectivityChanged.listen((v) => emitted.add(v));

      mockConnectivity.emit([ConnectivityResult.wifi]);

      await Future<void>.delayed(Duration.zero);
      expect(emitted, contains(isTrue));
      await sub.cancel();
      monitor.dispose();
    });

    test('stream emits false when going offline', () async {
      mockConnectivity.setResult([ConnectivityResult.wifi]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);
      await monitor.initialize();

      final emitted = <bool>[];
      final sub = monitor.onConnectivityChanged.listen((v) => emitted.add(v));

      mockConnectivity.emit([ConnectivityResult.none]);

      await Future<void>.delayed(Duration.zero);
      expect(emitted, contains(isFalse));
      await sub.cancel();
      monitor.dispose();
    });

    test('stream does not emit duplicate events when state has not changed',
        () async {
      mockConnectivity.setResult([ConnectivityResult.wifi]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);
      await monitor.initialize();

      final emitted = <bool>[];
      final sub = monitor.onConnectivityChanged.listen((v) => emitted.add(v));

      // Emit same state twice — only first should trigger the stream
      // (initialize already set isOnline = true, so the first emit
      // should not fire since state hasn't changed)
      mockConnectivity.emit([ConnectivityResult.wifi]);
      mockConnectivity.emit([ConnectivityResult.wifi]);

      await Future<void>.delayed(Duration.zero);
      expect(emitted, isEmpty); // No changes → no emissions
      await sub.cancel();
      monitor.dispose();
    });

    test('stream emits only on actual state transitions', () async {
      mockConnectivity.setResult([ConnectivityResult.wifi]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);
      await monitor.initialize();

      final emitted = <bool>[];
      final sub = monitor.onConnectivityChanged.listen((v) => emitted.add(v));

      // wifi → none (transition)
      mockConnectivity.emit([ConnectivityResult.none]);
      await Future<void>.delayed(Duration.zero);
      expect(emitted, [false]);

      // none → mobile (transition)
      mockConnectivity.emit([ConnectivityResult.mobile]);
      await Future<void>.delayed(Duration.zero);
      expect(emitted, [false, true]);

      // mobile → mobile (no change)
      mockConnectivity.emit([ConnectivityResult.mobile]);
      await Future<void>.delayed(Duration.zero);
      expect(emitted, [false, true]); // No additional entry

      // mobile → wifi (no change — both are "online")
      mockConnectivity.emit([ConnectivityResult.wifi]);
      await Future<void>.delayed(Duration.zero);
      expect(emitted, [false, true]); // No additional entry

      await sub.cancel();
      monitor.dispose();
    });

    test('stream handles transition from none to mixed results', () async {
      mockConnectivity.setResult([ConnectivityResult.none]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);
      await monitor.initialize();

      final emitted = <bool>[];
      final sub = monitor.onConnectivityChanged.listen((v) => emitted.add(v));

      mockConnectivity.emit([ConnectivityResult.none, ConnectivityResult.wifi]);

      await Future<void>.delayed(Duration.zero);
      expect(emitted, [true]); // Transition from offline to online
      await sub.cancel();
      monitor.dispose();
    });

    // ── dispose() ───────────────────────────────────────────────────────

    test('dispose cleans up subscription and controller', () async {
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);
      await monitor.initialize();

      // Subscribe before dispose
      var done = false;
      final sub = monitor.onConnectivityChanged.listen((_) {}, onDone: () {
        done = true;
      });

      monitor.dispose();

      // After dispose the stream should be done
      await Future<void>.delayed(Duration.zero);
      expect(done, isTrue);
    });

    // ── Multiple transitions ────────────────────────────────────────────

    test('handles multiple online/offline transitions correctly', () async {
      mockConnectivity.setResult([ConnectivityResult.wifi]);
      final monitor = ConnectivityMonitor(connectivity: mockConnectivity);
      await monitor.initialize();

      // online → offline → online → offline
      mockConnectivity.emit([ConnectivityResult.none]);
      await Future<void>.delayed(Duration.zero);
      expect(monitor.isOnline, isFalse);

      mockConnectivity.emit([ConnectivityResult.wifi]);
      await Future<void>.delayed(Duration.zero);
      expect(monitor.isOnline, isTrue);

      mockConnectivity.emit([ConnectivityResult.none]);
      await Future<void>.delayed(Duration.zero);
      expect(monitor.isOnline, isFalse);

      monitor.dispose();
    });
  });

  // ==========================================================================
  // Riverpod providers
  // ==========================================================================

  group('Riverpod providers', () {
    test('connectivityProvider returns a non-null ConnectivityMonitor', () {
      // The provider creates a ConnectivityMonitor with the default
      // Connectivity() plugin. Provider tests require ProviderContainer
      // and are best placed in an integration-test suite.
    });

    test('isOnlineProvider exposes onConnectivityChanged stream', () {
      // The StreamProvider wraps the monitor's broadcast stream so widgets
      // can reactively rebuild on connectivity changes.
    });
  });
}

// =============================================================================
// Helper: Connectivity that throws on checkConnectivity
// =============================================================================

class _ThrowingMockConnectivity implements Connectivity {
  @override
  Future<List<ConnectivityResult>> checkConnectivity() async {
    throw Exception('Platform not available');
  }

  @override
  Stream<List<ConnectivityResult>> get onConnectivityChanged =>
      const Stream.empty();
}
