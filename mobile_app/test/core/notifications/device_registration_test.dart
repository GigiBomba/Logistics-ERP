import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import 'package:operion_mobile/core/network/endpoints/device_endpoints.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/notifications/device_registration.dart';
import 'package:operion_mobile/core/notifications/push_service.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Mocks
// ─────────────────────────────────────────────────────────────────────────────

/// A controllable fake [DeviceEndpoints] using `implements` to avoid
/// the private [ApiClient._] constructor.
class MockDeviceEndpoints implements DeviceEndpoints {
  @override
  final ApiClient client;

  /// If non-null, [registerDevice] will throw this error.
  Object? registerError;

  /// If non-null, [unregisterDevice] will throw this error.
  Object? unregisterError;

  /// Records the last call to [registerDevice].
  String? lastRegisterToken;
  String? lastRegisterPlatform;
  bool registerCalled = false;

  /// Records the last call to [unregisterDevice].
  bool unregisterCalled = false;

  MockDeviceEndpoints()
      : client = ApiClient.create(
          baseUrl: 'https://test.example.com',
          getAccessToken: () async => null,
          getRefreshToken: () async => null,
          saveTokens: (_, __) async {},
          clearTokens: () async {},
        );

  @override
  Future<Response> registerDevice(
    String token,
    String platform, {
    String? deviceId,
    String? deviceName,
  }) async {
    registerCalled = true;
    lastRegisterToken = token;
    lastRegisterPlatform = platform;
    if (registerError != null) throw registerError!;
    return Response(
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
      data: {'status': 'registered'},
    );
  }

  @override
  Future<Response> unregisterDevice() async {
    unregisterCalled = true;
    if (unregisterError != null) throw unregisterError!;
    return Response(
      requestOptions: RequestOptions(path: ''),
      statusCode: 200,
      data: {'status': 'unregistered'},
    );
  }
}

/// A controllable fake [PushService] using `implements` to avoid the
/// need for a real [FirebaseMessaging] instance.
class MockPushService implements PushService {
  /// The token returned by the [token] getter.
  String? _token;

  /// Overrides the return value of [getToken] when set; otherwise uses [_token].
  String? getTokenOverride;

  /// If non-null, [getToken] will throw this error.
  Object? getTokenError;

  /// How many times [getToken] was called.
  int getTokenCallCount = 0;

  final _notificationController = StreamController<PushNotification>.broadcast();
  final _tokenController = StreamController<String>.broadcast();

  @override
  String? get token => _token;

  set token(String? t) => _token = t;

  @override
  Stream<PushNotification> get onNotification => _notificationController.stream;

  @override
  Stream<String> get onTokenRefresh => _tokenController.stream;

  @override
  Future<String?> getToken() async {
    getTokenCallCount++;
    if (getTokenError != null) throw getTokenError!;
    return getTokenOverride ?? _token;
  }

  @override
  Future<bool> requestPermission() async => true;

  @override
  void handleNotificationTap(RemoteMessage message) {}

  @override
  Future<void> initialize() async {
    // No-op in tests.
  }

  @override
  void dispose() {
    _notificationController.close();
    _tokenController.close();
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  group('DeviceRegistration', () {
    late MockDeviceEndpoints mockEndpoints;
    late MockPushService mockPushService;
    late DeviceRegistration registration;

    setUp(() {
      mockEndpoints = MockDeviceEndpoints();
      mockPushService = MockPushService();
      registration = DeviceRegistration(mockEndpoints, mockPushService);
    });

    // ── register() ───────────────────────────────

    group('register()', () {
      test('registers device with token and platform', () async {
        mockPushService.token = 'fcm-token-abc';

        await registration.register();

        expect(mockEndpoints.registerCalled, isTrue);
        expect(mockEndpoints.lastRegisterToken, 'fcm-token-abc');
        expect(
          mockEndpoints.lastRegisterPlatform,
          isIn(['ios', 'android', 'unknown']),
        );
      });

      test('calls getToken when token property is null', () async {
        // Make getToken() return a token even when the property is null.
        mockPushService.getTokenOverride = 'fcm-token-from-get';

        await registration.register();

        expect(mockPushService.getTokenCallCount, greaterThan(0));
        expect(mockEndpoints.registerCalled, isTrue);
        expect(mockEndpoints.lastRegisterToken, 'fcm-token-from-get');
      });

      test('skips registration when no token available', () async {
        mockPushService.token = null;
        mockPushService.getTokenOverride = null;

        await registration.register();

        expect(mockEndpoints.registerCalled, isFalse);
      });

      test('skips registration when token is empty string', () async {
        mockPushService.token = '';

        await registration.register();

        expect(mockEndpoints.registerCalled, isFalse);
      });

      test('token from getToken is used when token property is null', () async {
        mockPushService.getTokenOverride = 'get-token-value';

        await registration.register();

        expect(mockEndpoints.lastRegisterToken, 'get-token-value');
      });

      test('skips registration when both token and getToken return null', () async {
        mockPushService.token = null;
        mockPushService.getTokenOverride = null;

        await registration.register();

        expect(mockEndpoints.registerCalled, isFalse);
      });

      test('handles DioException (bad response) during registration', () async {
        mockPushService.token = 'fcm-token-abc';
        mockEndpoints.registerError = DioException(
          requestOptions: RequestOptions(path: ''),
          type: DioExceptionType.badResponse,
          response: Response(
            requestOptions: RequestOptions(path: ''),
            statusCode: 500,
          ),
        );

        // Should not throw
        await registration.register();

        expect(mockEndpoints.registerCalled, isTrue);
      });

      test('handles network timeout during registration', () async {
        mockPushService.token = 'fcm-token-abc';
        mockEndpoints.registerError = DioException(
          requestOptions: RequestOptions(path: ''),
          type: DioExceptionType.connectionTimeout,
        );

        // Should not throw
        await registration.register();

        expect(mockEndpoints.registerCalled, isTrue);
      });

      test('handles generic exception during registration', () async {
        mockPushService.token = 'fcm-token-abc';
        mockEndpoints.registerError = Exception('unexpected error');

        // Should not throw
        await registration.register();

        expect(mockEndpoints.registerCalled, isTrue);
      });
    });

    // ── unregister() ─────────────────────────────

    group('unregister()', () {
      test('unregisters device when token exists', () async {
        mockPushService.token = 'fcm-token-abc';

        await registration.unregister();

        expect(mockEndpoints.unregisterCalled, isTrue);
      });

      test('skips unregister when token is null', () async {
        mockPushService.token = null;

        await registration.unregister();

        expect(mockEndpoints.unregisterCalled, isFalse);
      });

      test('handles DioException during unregistration', () async {
        mockPushService.token = 'fcm-token-abc';
        mockEndpoints.unregisterError = DioException(
          requestOptions: RequestOptions(path: ''),
          type: DioExceptionType.badResponse,
          response: Response(
            requestOptions: RequestOptions(path: ''),
            statusCode: 500,
          ),
        );

        await registration.unregister();

        expect(mockEndpoints.unregisterCalled, isTrue);
      });

      test('handles network timeout during unregistration', () async {
        mockPushService.token = 'fcm-token-abc';
        mockEndpoints.unregisterError = DioException(
          requestOptions: RequestOptions(path: ''),
          type: DioExceptionType.connectionTimeout,
        );

        await registration.unregister();

        expect(mockEndpoints.unregisterCalled, isTrue);
      });

      test('handles generic exception during unregistration', () async {
        mockPushService.token = 'fcm-token-abc';
        mockEndpoints.unregisterError = Exception('unexpected');

        await registration.unregister();

        expect(mockEndpoints.unregisterCalled, isTrue);
      });
    });

    // ── Combined scenarios ───────────────────────

    group('combined scenarios', () {
      test('register then unregister works', () async {
        mockPushService.token = 'fcm-token-abc';

        await registration.register();
        expect(mockEndpoints.registerCalled, isTrue);

        await registration.unregister();
        expect(mockEndpoints.unregisterCalled, isTrue);
      });

      test('register after network failure retries successfully', () async {
        mockPushService.token = 'fcm-token-abc';

        // First attempt fails
        mockEndpoints.registerError = DioException(
          requestOptions: RequestOptions(path: ''),
          type: DioExceptionType.connectionTimeout,
        );
        await registration.register();
        expect(mockEndpoints.registerCalled, isTrue);

        // Reset and retry – succeeds
        mockEndpoints.registerCalled = false;
        mockEndpoints.registerError = null;
        await registration.register();
        expect(mockEndpoints.registerCalled, isTrue);
        expect(mockEndpoints.lastRegisterToken, 'fcm-token-abc');
      });

      test('register then unregister after token cleared', () async {
        mockPushService.token = 'fcm-token-abc';

        await registration.register();
        expect(mockEndpoints.registerCalled, isTrue);

        // Clear token — unregister skips
        mockPushService.token = null;
        mockEndpoints.unregisterCalled = false;

        await registration.unregister();
        expect(mockEndpoints.unregisterCalled, isFalse);
      });
    });
  });
}
