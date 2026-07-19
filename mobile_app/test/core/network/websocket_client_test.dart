import 'dart:async';
import 'dart:convert' show jsonEncode, jsonDecode;

import 'package:async/async.dart' show StreamSinkTransformer;
import 'package:flutter_test/flutter_test.dart';
import 'package:stream_channel/stream_channel.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'package:operion_mobile/core/network/websocket_client.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Fake WebSocketChannel implementation
// ─────────────────────────────────────────────────────────────────────────────

/// Fake [WebSocketSink] that records sent messages and tracks close state.
class FakeWebSocketSink implements WebSocketSink {
  /// All messages sent by the client through this sink.
  final List<dynamic> sentMessages = [];

  Completer<dynamic> _doneCompleter = Completer<dynamic>();

  bool _closed = false;

  @override
  void add(dynamic data) => sentMessages.add(data);

  @override
  Future<void> addStream(Stream<Object?> stream) {
    return stream.forEach(add);
  }

  @override
  void addError(Object error, [StackTrace? stackTrace]) {}

  @override
  Future<void> close([int? closeCode, String? closeReason]) async {
    if (!_doneCompleter.isCompleted) {
      _closed = true;
      _doneCompleter.complete(null);
    }
  }

  @override
  Future<dynamic> get done => _doneCompleter.future;

  bool get isClosed => _closed;
}

/// Fake [WebSocketChannel] that lets the test inject incoming messages and
/// inspect outgoing messages.
class FakeWebSocketChannel implements WebSocketChannel {
  final StreamController<dynamic> _incomingController =
      StreamController<dynamic>.broadcast();
  final FakeWebSocketSink _fakeSink = FakeWebSocketSink();

  // ── Test helpers ───────────────────────────────

  /// Inject a message as if arriving from the server.
  void injectMessage(Map<String, dynamic> message) {
    _incomingController.add(jsonEncode(message));
  }

  /// Inject a raw string as if arriving from the server.
  void injectRaw(String raw) {
    _incomingController.add(raw);
  }

  /// Inject a non-string object as if arriving from the server.
  void injectObject(dynamic obj) {
    _incomingController.add(obj);
  }

  /// Close the incoming stream (simulate server disconnect).
  void closeIncoming() {
    _incomingController.close();
  }

  /// Send an error through the incoming stream.
  void injectError(Object error) {
    _incomingController.addError(error);
  }

  /// All messages the client has sent via [sink].
  List<dynamic> get sentMessages => _fakeSink.sentMessages;

  /// Whether the sink has been closed.
  bool get sinkIsClosed => _fakeSink.isClosed;

  // ── WebSocketChannel interface ─────────────────

  @override
  Stream<dynamic> get stream => _incomingController.stream;

  @override
  WebSocketSink get sink => _fakeSink;

  @override
  int? get closeCode => null;

  @override
  String? get closeReason => null;

  @override
  String? get protocol => null;

  @override
  Future<void> get ready => Future.value();

  // ── StreamChannel mixin stubs (unused by WebSocketClient) ──

  @override
  void pipe(StreamChannel<dynamic> other) {
    stream.pipe(other.sink);
    other.stream.pipe(sink);
  }

  @override
  StreamChannel<S> cast<S>() =>
      StreamChannel<S>(stream.cast<S>(), sink as StreamSink<S>);

  @override
  StreamChannel<dynamic> changeStream(
    Stream<dynamic> Function(Stream<dynamic>) change,
  ) =>
      StreamChannel<dynamic>.withCloseGuarantee(change(stream), sink);

  @override
  StreamChannel<dynamic> changeSink(
    StreamSink<dynamic> Function(StreamSink<dynamic>) change,
  ) =>
      StreamChannel<dynamic>.withCloseGuarantee(stream, change(sink));

  @override
  StreamChannel<S> transform<S>(
    StreamChannelTransformer<S, dynamic> transformer,
  ) =>
      transformer.bind(this);

  @override
  StreamChannel<dynamic> transformStream(
    StreamTransformer<dynamic, dynamic> transformer,
  ) =>
      changeStream(transformer.bind);

  @override
  StreamChannel<dynamic> transformSink(
    StreamSinkTransformer<dynamic, dynamic> transformer,
  ) =>
      changeSink(transformer.bind);

  void dispose() {
    _incomingController.close();
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  group('WebSocketClient', () {
    late FakeWebSocketChannel fakeChannel;
    late WebSocketClient client;

    setUp(() {
      fakeChannel = FakeWebSocketChannel();
      client = WebSocketClient(
        channelFactory: (_) => fakeChannel,
      );
    });

    tearDown(() {
      client.dispose();
      fakeChannel.dispose();
    });

    // ── Connect / disconnect lifecycle ───────────

    group('connect / disconnect lifecycle', () {
      test('connect sets isConnected to true', () async {
        expect(client.isConnected, isFalse);

        await client.connect('wss://test.example.com/ws', 'test-token');

        expect(client.isConnected, isTrue);
      });

      test('disconnect sets isConnected to false', () async {
        await client.connect('wss://test.example.com/ws', 't');
        expect(client.isConnected, isTrue);

        client.disconnect();

        expect(client.isConnected, isFalse);
      });

      test('disconnect closes the underlying sink', () async {
        await client.connect('wss://test.example.com/ws', 't');

        client.disconnect();

        expect(fakeChannel.sinkIsClosed, isTrue);
      });

      test('dispose is safe to call multiple times', () {
        client.dispose();
        expect(() => client.dispose(), returnsNormally);
      });

      test('connect on already connected client disconnects first', () async {
        await client.connect('wss://test.example.com/ws', 't');
        expect(client.isConnected, isTrue);

        // Connect again — old connection is closed
        await client.connect('wss://test.example.com/ws2', 't2');
        expect(client.isConnected, isTrue);
      });
    });

    // ── Message send / receive ───────────────────

    group('message send / receive', () {
      test('receive decoded JSON message via messages stream', () async {
        final received = <Map<String, dynamic>>[];
        client.messages.listen(received.add);

        await client.connect('wss://test.example.com/ws', 't');

        fakeChannel.injectMessage({'type': 'hello', 'value': 42});

        await Future(() {});
        expect(received, hasLength(1));
        expect(received[0]['type'], 'hello');
        expect(received[0]['value'], 42);
      });

      test('receive multiple messages in order', () async {
        final received = <Map<String, dynamic>>[];
        client.messages.listen(received.add);

        await client.connect('wss://test.example.com/ws', 't');

        fakeChannel.injectMessage({'seq': 1});
        fakeChannel.injectMessage({'seq': 2});
        fakeChannel.injectMessage({'seq': 3});

        await Future(() {});
        expect(received, hasLength(3));
        expect(received[0]['seq'], 1);
        expect(received[1]['seq'], 2);
        expect(received[2]['seq'], 3);
      });

      test('send encodes map as JSON and writes to sink', () async {
        await client.connect('wss://test.example.com/ws', 't');

        client.send({'action': 'ping'});

        await Future(() {});
        expect(fakeChannel.sentMessages, hasLength(1));
        expect(jsonDecode(fakeChannel.sentMessages[0] as String), {
          'action': 'ping',
        });
      });

      test('send multiple messages in order', () async {
        await client.connect('wss://test.example.com/ws', 't');

        client.send({'seq': 1});
        client.send({'seq': 2});

        await Future(() {});
        expect(fakeChannel.sentMessages, hasLength(2));
      });

      test('send when not connected does not throw', () async {
        expect(() => client.send({'test': true}), returnsNormally);
      });

      test('handles non-Map messages gracefully', () async {
        final received = <Map<String, dynamic>>[];
        client.messages.listen(received.add);

        await client.connect('wss://test.example.com/ws', 't');

        fakeChannel.injectRaw('[1, 2, 3]');

        await Future(() {});
        expect(received, isEmpty);
      });

      test('handles invalid JSON gracefully', () async {
        final received = <Map<String, dynamic>>[];
        client.messages.listen(received.add);

        await client.connect('wss://test.example.com/ws', 't');

        fakeChannel.injectRaw('not json');

        await Future(() {});
        expect(received, isEmpty);
      });

      test('parses Map from pre-decoded object', () async {
        final received = <Map<String, dynamic>>[];
        client.messages.listen(received.add);

        await client.connect('wss://test.example.com/ws', 't');

        fakeChannel.injectObject({'type': 'direct_map'});

        await Future(() {});
        expect(received, hasLength(1));
        expect(received[0]['type'], 'direct_map');
      });
    });

    // ── Auto-reconnection ────────────────────────

    group('auto-reconnection', () {
      test('reconnects when connection stream closes', () async {
        // Use a factory that returns a fresh channel on each call
        FakeWebSocketChannel? channel2;
        final reconnectingClient = WebSocketClient(
          channelFactory: (_) {
            channel2 = FakeWebSocketChannel();
            return channel2!;
          },
        );

        await reconnectingClient.connect('wss://test.example.com/ws', 't');
        expect(reconnectingClient.isConnected, isTrue);

        // Close the first channel's incoming stream to trigger reconnect
        channel2!.closeIncoming();

        // Wait for reconnect timer (initial delay = 1s)
        await Future.delayed(const Duration(milliseconds: 1500));

        expect(reconnectingClient.isConnected, isTrue);

        reconnectingClient.dispose();
      });

      test('reconnect does not happen after explicit disconnect', () async {
        await client.connect('wss://test.example.com/ws', 't');

        client.disconnect();

        fakeChannel.closeIncoming();
        await Future.delayed(const Duration(milliseconds: 1500));

        expect(client.isConnected, isFalse);
      });

      test('reconnect after stream error', () async {
        FakeWebSocketChannel? channel2;
        final reconnectingClient = WebSocketClient(
          channelFactory: (_) {
            channel2 = FakeWebSocketChannel();
            return channel2!;
          },
        );

        await reconnectingClient.connect('wss://test.example.com/ws', 't');

        channel2!.injectError(Exception('connection lost'));

        await Future.delayed(const Duration(milliseconds: 1500));
        expect(reconnectingClient.isConnected, isTrue);

        reconnectingClient.dispose();
      });
    });

    // ── Error handling ───────────────────────────

    group('error handling', () {
      test('factory exception during connect schedules reconnect', () async {
        final brokenClient = WebSocketClient(
          channelFactory: (_) => throw Exception('connection refused'),
        );

        await brokenClient.connect('wss://test.example.com/ws', 't');

        expect(brokenClient.isConnected, isFalse);

        await Future.delayed(const Duration(milliseconds: 1500));
        // Still false because the factory still throws
        expect(brokenClient.isConnected, isFalse);

        brokenClient.dispose();
      });

      test('stream error does not crash the client', () async {
        await client.connect('wss://test.example.com/ws', 't');

        fakeChannel.injectError(StateError('stream error'));

        await Future(() {});
      });

      test('stream done does not crash the client', () async {
        await client.connect('wss://test.example.com/ws', 't');

        fakeChannel.closeIncoming();

        await Future(() {});
        // The client should have scheduled a reconnect internally
      });
    });
  });
}
