import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/auth/token_manager.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/auth_endpoints.dart';
import 'package:operion_mobile/core/network/message_bus.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Fake implementations
// ─────────────────────────────────────────────────────────────────────────────

class _FakeSecureTokenStore implements SecureTokenStore {
  String? _accessToken;
  String? _refreshToken;
  String? _deviceId;
  bool _hasTokens = false;

  @override
  Future<void> saveTokens(String accessToken, String refreshToken) async {
    _accessToken = accessToken;
    _refreshToken = refreshToken;
    _hasTokens = accessToken.isNotEmpty;
  }

  @override
  Future<String?> getAccessToken() async => _accessToken;

  @override
  Future<String?> getRefreshToken() async => _refreshToken;

  @override
  Future<void> clearTokens() async {
    _accessToken = null;
    _refreshToken = null;
    _hasTokens = false;
  }

  @override
  Future<bool> hasTokens() async => _hasTokens;

  @override
  Future<String> getOrCreateDeviceId() async {
    _deviceId ??= 'test-device-uuid';
    return _deviceId!;
  }
}

class _FakeAuthEndpoints implements AuthEndpoints {
  @override
  final ApiClient client;

  Response Function()? onRefresh;

  _FakeAuthEndpoints({required this.client});

  @override
  Future<Response> login(String email, String password,
          {String? deviceId}) async =>
      _defaultResponse();

  @override
  Future<Response> refreshToken(String refreshToken) async =>
      onRefresh?.call() ?? _defaultResponse();

  @override
  Future<Response> logout() async => _defaultResponse();

  @override
  Future<Response> getMe() async => _defaultResponse();

  @override
  Future<Response> registerDevice({
    required String deviceId,
    required String platform,
    String? deviceName,
    String? fcmToken,
  }) async =>
      _defaultResponse();

  Response _defaultResponse() => Response(
        requestOptions: RequestOptions(path: ''),
        data: {'status': 'ok'},
        statusCode: 200,
      );
}

/// Creates a minimal ApiClient with cleared interceptors.
ApiClient _noopClient() {
  return ApiClient.create(
    baseUrl: 'https://test.com',
    getAccessToken: () async => null,
  );
}

/// Helper to create a refresh response.
Response _refreshResponse(String? accessToken, String? refreshToken) {
  final data = <String, dynamic>{};
  if (accessToken != null) data['accessToken'] = accessToken;
  if (refreshToken != null) data['refreshToken'] = refreshToken;
  return Response(
    requestOptions: RequestOptions(path: ''),
    data: data,
    statusCode: 200,
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  group('TokenManager', () {
    late _FakeSecureTokenStore store;
    late _FakeAuthEndpoints endpoints;
    late MessageBus bus;
    late TokenManager manager;

    setUp(() {
      store = _FakeSecureTokenStore();
      bus = MessageBus();
      endpoints = _FakeAuthEndpoints(client: _noopClient());
      manager = TokenManager(store, endpoints, bus);
    });

    tearDown(() {
      bus.dispose();
    });

    // ── initialize() ────────────────────────────────────────────────────

    test('initialize: no stored tokens → isAuthenticated false', () async {
      await manager.initialize();
      expect(manager.isAuthenticated, isFalse);
    });

    test('initialize: stored tokens → isAuthenticated true', () async {
      await store.saveTokens('at1', 'rt1');
      await manager.initialize();
      expect(manager.isAuthenticated, isTrue);
    });

    test('initialize: hasTokens result drives isAuthenticated', () async {
      // Store has tokens
      await store.saveTokens('at1', 'rt1');
      await manager.initialize();
      expect(manager.isAuthenticated, isTrue);

      // Clear and re-initialize
      await store.clearTokens();
      await manager.initialize();
      expect(manager.isAuthenticated, isFalse);
    });

    // ── saveTokens() ────────────────────────────────────────────────────

    test('saveTokens persists both tokens', () async {
      await manager.saveTokens('access123', 'refresh456');

      final access = await manager.getAccessToken();
      final refresh = await manager.getRefreshToken();
      expect(access, 'access123');
      expect(refresh, 'refresh456');
      expect(manager.isAuthenticated, isTrue);
    });

    test('saveTokens overwrites previous tokens', () async {
      await manager.saveTokens('old_access', 'old_refresh');
      await manager.saveTokens('new_access', 'new_refresh');

      final access = await manager.getAccessToken();
      final refresh = await manager.getRefreshToken();
      expect(access, 'new_access');
      expect(refresh, 'new_refresh');
    });

    // ── clearTokens() ───────────────────────────────────────────────────

    test('clearTokens removes both tokens and sets isAuthenticated false',
        () async {
      await manager.saveTokens('at1', 'rt1');
      await manager.clearTokens();

      final access = await manager.getAccessToken();
      final refresh = await manager.getRefreshToken();
      expect(access, isNull);
      expect(refresh, isNull);
      expect(manager.isAuthenticated, isFalse);
    });

    test('clearTokens on already cleared state does not error', () async {
      // Should not throw
      await manager.clearTokens();
      expect(manager.isAuthenticated, isFalse);
    });

    // ── getAccessToken() / getRefreshToken() ────────────────────────────

    test('getAccessToken returns null when no token stored', () async {
      final token = await manager.getAccessToken();
      expect(token, isNull);
    });

    test('getRefreshToken returns null when no token stored', () async {
      final token = await manager.getRefreshToken();
      expect(token, isNull);
    });

    test('getAccessToken returns stored value after saveTokens', () async {
      await manager.saveTokens('stored_at', 'stored_rt');
      final token = await manager.getAccessToken();
      expect(token, 'stored_at');
    });

    test('getRefreshToken returns stored value after saveTokens', () async {
      await manager.saveTokens('stored_at', 'stored_rt');
      final token = await manager.getRefreshToken();
      expect(token, 'stored_rt');
    });

    // ── tryRefresh() ────────────────────────────────────────────────────

    test('tryRefresh with no refresh token returns false', () async {
      final result = await manager.tryRefresh();
      expect(result, isFalse);
    });

    test('tryRefresh with empty refresh token returns false', () async {
      await manager.saveTokens('at1', '');
      final result = await manager.tryRefresh();
      expect(result, isFalse);
    });

    test('tryRefresh with valid refresh returns true and updates tokens',
        () async {
      await manager.saveTokens('at_old', 'rt_valid');

      endpoints.onRefresh = () => _refreshResponse('at_new', 'rt_new');

      final result = await manager.tryRefresh();

      expect(result, isTrue);
      final access = await manager.getAccessToken();
      final refresh = await manager.getRefreshToken();
      expect(access, 'at_new');
      expect(refresh, 'rt_new');
    });

    test('tryRefresh with only accessToken returned keeps old refresh',
        () async {
      await manager.saveTokens('at_old', 'rt_old');

      endpoints.onRefresh = () => _refreshResponse('at_new', null);

      final result = await manager.tryRefresh();

      expect(result, isTrue);
      final access = await manager.getAccessToken();
      final refresh = await manager.getRefreshToken();
      expect(access, 'at_new');
      // When no new refresh token is returned, the old refresh token is kept
      expect(refresh, 'rt_old');
    });

    test('tryRefresh with neither token returned returns false', () async {
      await manager.saveTokens('at_old', 'rt_old');

      endpoints.onRefresh = () => _refreshResponse(null, null);

      final result = await manager.tryRefresh();

      expect(result, isFalse);
      // Old tokens should be preserved when refresh fails
      final access = await manager.getAccessToken();
      expect(access, 'at_old');
    });

    test('tryRefresh on network error returns false and preserves old tokens',
        () async {
      await manager.saveTokens('at_old', 'rt_old');

      endpoints.onRefresh = () => throw DioException(
            requestOptions: RequestOptions(path: ''),
            type: DioExceptionType.connectionTimeout,
          );

      final result = await manager.tryRefresh();

      expect(result, isFalse);
      // Old tokens must be preserved on network error
      final access = await manager.getAccessToken();
      expect(access, 'at_old');
    });

    test('tryRefresh on 401 rejection returns false', () async {
      await manager.saveTokens('at_old', 'rt_old');

      endpoints.onRefresh = () => throw DioException(
            requestOptions: RequestOptions(path: ''),
            type: DioExceptionType.badResponse,
            response: Response(
              requestOptions: RequestOptions(path: ''),
              statusCode: 401,
            ),
          );

      final result = await manager.tryRefresh();

      expect(result, isFalse);
      // Old tokens should be preserved on 401 — AuthService handles clearing
      final access = await manager.getAccessToken();
      expect(access, 'at_old');
    });

    test('tryRefresh on generic exception returns false', () async {
      await manager.saveTokens('at_old', 'rt_old');

      endpoints.onRefresh = () => throw Exception('Unexpected error');

      final result = await manager.tryRefresh();

      expect(result, isFalse);
    });

    test('tryRefresh updates isAuthenticated to true on success', () async {
      await manager.saveTokens('at_old', 'rt_valid');

      endpoints.onRefresh = () => _refreshResponse('at_new', 'rt_new');

      expect(manager.isAuthenticated, isTrue);
      final result = await manager.tryRefresh();
      expect(result, isTrue);
      expect(manager.isAuthenticated, isTrue);
    });

    // ── isAuthenticated ─────────────────────────────────────────────────

    test('isAuthenticated is false by default', () {
      expect(manager.isAuthenticated, isFalse);
    });

    test('isAuthenticated reflects saveTokens/clearTokens lifecycle', () async {
      expect(manager.isAuthenticated, isFalse);

      await manager.saveTokens('at1', 'rt1');
      expect(manager.isAuthenticated, isTrue);

      await manager.clearTokens();
      expect(manager.isAuthenticated, isFalse);
    });
  });
}
