import 'dart:async';
import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:math';

import 'package:web_socket_channel/web_socket_channel.dart';

/// A WebSocket client with built-in auto-reconnect (exponential backoff) and
/// heartbeat keep-alive.
///
/// Usage:
/// ```dart
/// final ws = WebSocketClient();
/// await ws.connect('wss://api.operion.io/ws', token);
/// ws.messages.listen((msg) { ... });
/// ws.send({'type': 'ping'});
/// ws.disconnect();
/// ```
class WebSocketClient {
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  Timer? _heartbeatTimer;
  Timer? _reconnectTimer;

  final StreamController<Map<String, dynamic>> _messageController =
      StreamController<Map<String, dynamic>>.broadcast();

  /// Factory for creating the underlying WebSocket channel.
  ///
  /// Defaults to [WebSocketChannel.connect]. Override in tests to inject a
  /// fake channel without establishing a real connection.
  final WebSocketChannel Function(Uri uri) _channelFactory;

  /// The URL the client is connected to (or attempting to reconnect to).
  String? _url;
  String? _token;

  int _reconnectAttempt = 0;
  static const _maxReconnectDelay = Duration(seconds: 30);
  static const _heartbeatInterval = Duration(seconds: 30);
  static const _initialReconnectDelay = Duration(seconds: 1);

  /// Whether the client should attempt to reconnect after a disconnect.
  bool _shouldReconnect = false;

  /// Stream of decoded JSON messages from the server.
  Stream<Map<String, dynamic>> get messages => _messageController.stream;

  /// Whether the WebSocket is currently connected.
  bool get isConnected => _channel != null;

  /// Creates a new WebSocket client.
  ///
  /// The optional [channelFactory] allows injecting a custom channel creator
  /// for testing; it defaults to [WebSocketChannel.connect].
  WebSocketClient({WebSocketChannel Function(Uri uri)? channelFactory})
      : _channelFactory = channelFactory ?? WebSocketChannel.connect;

  // ── Lifecycle ─────────────────────────────────

  /// Connect to [url] passing [token] as a query parameter for authentication.
  ///
  /// The token is appended as `?token=<token>`. Any existing connection is
  /// closed first.
  Future<void> connect(String url, String token) async {
    disconnect();
    _url = url;
    _token = token;
    _shouldReconnect = true;
    _reconnectAttempt = 0;
    await _doConnect();
  }

  Future<void> _doConnect() async {
    try {
      final uri = Uri.parse(_url!).replace(queryParameters: {
        'token': _token,
      });
      _channel = _channelFactory(uri);
      _subscription = _channel!.stream.listen(
        _onData,
        onError: _onError,
        onDone: _onDone,
        cancelOnError: false,
      );
      _startHeartbeat();
      _reconnectAttempt = 0;
      developer.log('WebSocket connected to $_url', name: 'WebSocketClient');
    } catch (e) {
      developer.log('WebSocket connect failed: $e', name: 'WebSocketClient');
      _scheduleReconnect();
    }
  }

  /// Send a JSON-encodable map through the WebSocket.
  void send(Map<String, dynamic> data) {
    if (_channel != null) {
      _channel!.sink.add(jsonEncode(data));
    } else {
      developer.log(
        'WebSocketClient: cannot send – not connected',
        name: 'WebSocketClient',
      );
    }
  }

  /// Gracefully close the WebSocket connection (no reconnect).
  void disconnect() {
    _shouldReconnect = false;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _stopHeartbeat();
    _subscription?.cancel();
    _subscription = null;
    _channel?.sink.close();
    _channel = null;
    developer.log('WebSocket disconnected', name: 'WebSocketClient');
  }

  /// Release all resources. The instance must not be used after this call.
  void dispose() {
    disconnect();
    _messageController.close();
  }

  // ── Internal handlers ─────────────────────────

  void _onData(dynamic raw) {
    try {
      final decoded = (raw is String) ? jsonDecode(raw) : raw;
      if (decoded is Map<String, dynamic>) {
        _messageController.add(decoded);
      } else {
        developer.log('WebSocketClient: unexpected message type: ${decoded.runtimeType}',
          name: 'WebSocketClient');
      }
    } catch (e) {
      developer.log(
        'WebSocketClient: failed to decode message – $e',
        name: 'WebSocketClient',
      );
    }
  }

  void _onError(Object error) {
    developer.log('WebSocket error: $error', name: 'WebSocketClient');
    _scheduleReconnect();
  }

  void _onDone() {
    developer.log('WebSocket connection closed', name: 'WebSocketClient');
    _channel = null;
    _stopHeartbeat();
    if (_shouldReconnect) {
      _scheduleReconnect();
    }
  }

  // ── Reconnect with exponential backoff ────────

  void _scheduleReconnect() {
    if (!_shouldReconnect) return;

    _reconnectTimer?.cancel();
    final delay = Duration(
      seconds: min(
        _initialReconnectDelay.inSeconds * (1 << _reconnectAttempt),
        _maxReconnectDelay.inSeconds,
      ),
    );
    _reconnectAttempt++;
    developer.log(
      'WebSocketClient: reconnecting in ${delay.inSeconds}s '
      '(attempt $_reconnectAttempt)',
      name: 'WebSocketClient',
    );
    _reconnectTimer = Timer(delay, _doConnect);
  }

  // ── Heartbeat ─────────────────────────────────

  void _startHeartbeat() {
    _stopHeartbeat();
    _heartbeatTimer = Timer.periodic(_heartbeatInterval, (_) {
      send({'type': 'ping'});
    });
  }

  void _stopHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;
  }
}
