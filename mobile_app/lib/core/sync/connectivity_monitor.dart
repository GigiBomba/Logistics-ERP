import 'dart:async';
import 'dart:developer' as developer;

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Reactive connectivity monitor that wraps [connectivity_plus].
///
/// Exposes:
/// - [isOnline] – a synchronous snapshot of the current state.
/// - [onConnectivityChanged] – a broadcast stream that emits `true` (online)
///   or `false` (offline) whenever the network state changes.
///
/// The initial state is optimistically `true`; after [initialize] completes,
/// it reflects the actual platform-reported state.
class ConnectivityMonitor {
  final Connectivity _connectivity;
  final StreamController<bool> _controller =
      StreamController<bool>.broadcast();

  StreamSubscription? _connectivitySubscription;
  bool _isOnline = true;

  /// Whether the device currently has network connectivity.
  bool get isOnline => _isOnline;

  /// Broadcast stream that fires `true` (online) or `false` (offline).
  Stream<bool> get onConnectivityChanged => _controller.stream;

  ConnectivityMonitor({Connectivity? connectivity})
      : _connectivity = connectivity ?? Connectivity();

  /// Initialises the monitor by reading the current connectivity state and
  /// listening for further changes.
  ///
  /// Must be called once before using [onConnectivityChanged].
  Future<void> initialize() async {
    try {
      final results = await _connectivity.checkConnectivity();
      _updateState(results);
    } catch (e) {
      developer.log(
        'ConnectivityMonitor.initialize: $e',
        name: 'ConnectivityMonitor',
      );
      // Keep optimistic true on failure so the app is not blocked.
    }

    // Listen for ongoing connectivity changes.
    _connectivitySubscription =
        _connectivity.onConnectivityChanged.listen((results) {
      _updateState(results);
    });
  }

  /// Updates the internal state and fires the stream when the value changes.
  void _updateState(List<ConnectivityResult> results) {
    // Online if at least one result is NOT ConnectivityResult.none.
    final online = results.any((r) => r != ConnectivityResult.none);
    if (online != _isOnline) {
      _isOnline = online;
      developer.log(
        'ConnectivityMonitor: ${online ? "online" : "offline"}',
        name: 'ConnectivityMonitor',
      );
      _controller.add(online);
    }
  }

  /// Tears down the stream controller.
  ///
  /// After calling this the monitor should no longer be used.
  void dispose() {
    _connectivitySubscription?.cancel();
    _controller.close();
  }
}

// ── Riverpod providers ───────────────────────────────────────────────

/// Provides the singleton [ConnectivityMonitor] instance.
final connectivityProvider = Provider<ConnectivityMonitor>((ref) {
  final monitor = ConnectivityMonitor();
  monitor.initialize();
  ref.onDispose(() => monitor.dispose());
  return monitor;
});

/// Reactive online/offline stream backed by [connectivityProvider].
///
/// Emits `true` when the device goes online, `false` when it goes offline.
/// The initial value is obtained by calling [ConnectivityMonitor.initialize]
/// inside a [ref.onResume] or app-startup logic.
final isOnlineProvider = StreamProvider<bool>((ref) {
  final monitor = ref.watch(connectivityProvider);
  return monitor.onConnectivityChanged;
});
