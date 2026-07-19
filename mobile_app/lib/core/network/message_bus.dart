import 'dart:async';

/// A typed in-app event bus for real-time notifications received via WebSocket
/// or other channels.
///
/// Components can subscribe to the global [MessageBus.stream] and filter on
/// specific [BusEvent] types using `whereType<T>()`.
///
/// Usage:
/// ```dart
/// final bus = MessageBus();
/// bus.stream.whereType<StatusChangeEvent>().listen((event) {
///   print('Transport ${event.transportId} is now ${event.newStatus}');
/// });
/// bus.emit(StatusChangeEvent('tr-42', 'delivered'));
/// ```
class MessageBus {
  bool _isDisposed = false;
  final StreamController<BusEvent> _controller =
      StreamController<BusEvent>.broadcast();

  /// The broadcast stream of all bus events.
  Stream<BusEvent> get stream => _controller.stream;

  /// Publish an [event] to all subscribers.
  ///
  /// If the bus has been disposed, calling this method will throw an [Exception]
  /// instead of silently dropping the event or crashing with a [StateError].
  void emit(BusEvent event) {
    if (_isDisposed) {
      throw Exception('Cannot emit events after dispose');
    }
    _controller.add(event);
  }

  /// Close the underlying stream controller and mark the bus as disposed.
  /// No further events can be emitted.
  void dispose() {
    _isDisposed = true;
    _controller.close();
  }
}

// ── Event types ─────────────────────────────────

/// Base sealed class for all bus events.
sealed class BusEvent {
  const BusEvent();
}

/// Emitted when a new chat message arrives for the current user.
class NewMessageEvent extends BusEvent {
  final String threadId;
  NewMessageEvent(this.threadId);
}

/// Emitted when the status of a transport changes.
class StatusChangeEvent extends BusEvent {
  final String transportId;
  final String newStatus;
  StatusChangeEvent(this.transportId, this.newStatus);
}

/// Emitted when a vehicle's GPS position is received.
class FleetPositionEvent extends BusEvent {
  final String vehicleId;
  final double lat;
  final double lng;
  FleetPositionEvent(this.vehicleId, this.lat, this.lng);
}

/// Emitted when the device's connectivity status changes.
class ConnectivityChangedEvent extends BusEvent {
  final bool isOnline;
  ConnectivityChangedEvent(this.isOnline);
}

/// Emitted when the server forces the current user to log out (e.g. session
/// revoked or refresh token expired).
class ForceLogoutEvent extends BusEvent {
  const ForceLogoutEvent();
}
