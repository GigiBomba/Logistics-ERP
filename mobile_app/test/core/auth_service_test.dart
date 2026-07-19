import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/auth/auth_service.dart';
import 'package:operion_mobile/core/auth/token_manager.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/auth_endpoints.dart';
import 'package:operion_mobile/core/network/message_bus.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/shared/models/user.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Fake implementations
// ─────────────────────────────────────────────────────────────────────────────

class _FakeSecureTokenStore implements SecureTokenStore {
  String? _accessToken;
  String? _refreshToken;
  String? _deviceId;

  @override
  Future<void> saveTokens(String accessToken, String refreshToken) async {
    _accessToken = accessToken;
    _refreshToken = refreshToken;
  }

  @override
  Future<String?> getAccessToken() async => _accessToken;

  @override
  Future<String?> getRefreshToken() async => _refreshToken;

  @override
  Future<void> clearTokens() async {
    _accessToken = null;
    _refreshToken = null;
  }

  @override
  Future<bool> hasTokens() async =>
      _accessToken != null && _accessToken!.isNotEmpty;

  @override
  Future<String> getOrCreateDeviceId() async {
    _deviceId ??= 'test-device-uuid';
    return _deviceId!;
  }
}

class _FakeAuthEndpoints implements AuthEndpoints {
  @override
  final ApiClient client;

  Response Function()? onLogin;
  Response Function()? onRefresh;
  Response Function()? onLogout;
  Response Function()? onGetMe;
  Response Function()? onRegisterDevice;

  _FakeAuthEndpoints({required this.client});

  Response _defaultResponse() => Response(
        requestOptions: RequestOptions(path: ''),
        data: {'status': 'ok'},
        statusCode: 200,
      );

  @override
  Future<Response> login(String email, String password,
          {String? deviceId}) async =>
      onLogin?.call() ?? _defaultResponse();

  @override
  Future<Response> refreshToken(String refreshToken) async =>
      onRefresh?.call() ?? _defaultResponse();

  @override
  Future<Response> logout() async => onLogout?.call() ?? _defaultResponse();

  @override
  Future<Response> getMe() async => onGetMe?.call() ?? _defaultResponse();

  @override
  Future<Response> registerDevice({
    required String deviceId,
    required String platform,
    String? deviceName,
    String? fcmToken,
  }) async =>
      onRegisterDevice?.call() ?? _defaultResponse();
}

/// Creates a minimal ApiClient with cleared interceptors — used only so the
/// fake AuthEndpoints satisfies the `client` field requirement.
ApiClient _noopClient() {
  return ApiClient.create(
    baseUrl: 'https://test.com',
    getAccessToken: () async => null,
  );
}

/// Helper to create a successful user response for the getMe endpoint.
Response _userResponse() => Response(
      requestOptions: RequestOptions(path: ''),
      data: {
        'user': {
          'id': 'u1',
          'email': 'test@test.com',
          'fullName': 'Test User',
          'role': 'driver',
          'companyId': 'c1',
        }
      },
      statusCode: 200,
    );

/// Helper to create a login response with tokens.
/// Uses a sentinel value to distinguish "not provided" from "explicitly null".
Response _loginResponse({
  bool includeAccessToken = true,
  bool includeRefreshToken = true,
  String? accessToken,
  String? refreshToken,
  bool useSnakeCase = false,
}) {
  final data = <String, dynamic>{};
  if (includeAccessToken) {
    if (useSnakeCase) {
      data['access_token'] = accessToken ?? 'at1';
    } else {
      data['accessToken'] = accessToken ?? 'at1';
    }
  }
  if (includeRefreshToken) {
    if (useSnakeCase) {
      data['refresh_token'] = refreshToken ?? 'rt1';
    } else {
      data['refreshToken'] = refreshToken ?? 'rt1';
    }
  }
  return Response(
    requestOptions: RequestOptions(path: ''),
    data: data,
    statusCode: 200,
  );
}

/// Helper to create a DioException with a given type and status code.
DioException _dioException({
  required DioExceptionType type,
  int? statusCode,
  dynamic data,
}) {
  return DioException(
    requestOptions: RequestOptions(path: ''),
    type: type,
    response: data != null || statusCode != null
        ? Response(
            requestOptions: RequestOptions(path: ''),
            data: data,
            statusCode: statusCode,
          )
        : null,
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  group('AuthService', () {
    late _FakeSecureTokenStore tokenStore;
    late _FakeAuthEndpoints fakeEndpoints;
    late TokenManager tokenManager;
    late MessageBus bus;
    late AuthService authService;

    setUp(() {
      tokenStore = _FakeSecureTokenStore();
      bus = MessageBus();
      fakeEndpoints = _FakeAuthEndpoints(client: _noopClient());
      tokenManager = TokenManager(tokenStore, fakeEndpoints, bus);
      authService = AuthService(fakeEndpoints, tokenManager, tokenStore);
    });

    tearDown(() {
      bus.dispose();
    });

    // ── login() ─────────────────────────────────────────────────────────

    test('login with valid credentials returns AuthResult(success: true, user)',
        () async {
      fakeEndpoints.onLogin = () => _loginResponse();
      fakeEndpoints.onGetMe = () => _userResponse();

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isTrue);
      expect(result.user, isA<User>());
      expect(result.user!.email, 'test@test.com');
      expect(result.errorMessage, isNull);
    });

    test(
        'login with camelCase token keys (accessToken/refreshToken) parses correctly',
        () async {
      fakeEndpoints.onLogin = () => _loginResponse(
            accessToken: 'camel_at',
            refreshToken: 'camel_rt',
            useSnakeCase: false,
          );
      fakeEndpoints.onGetMe = () => _userResponse();

      await authService.login('test@test.com', 'password');

      final access = await tokenManager.getAccessToken();
      final refresh = await tokenManager.getRefreshToken();
      expect(access, 'camel_at');
      expect(refresh, 'camel_rt');
    });

    test(
        'login with snake_case token keys (access_token/refresh_token) parses correctly',
        () async {
      fakeEndpoints.onLogin = () => _loginResponse(
            accessToken: 'snake_at',
            refreshToken: 'snake_rt',
            useSnakeCase: true,
          );
      fakeEndpoints.onGetMe = () => _userResponse();

      await authService.login('test@test.com', 'password');

      final access = await tokenManager.getAccessToken();
      final refresh = await tokenManager.getRefreshToken();
      expect(access, 'snake_at');
      expect(refresh, 'snake_rt');
    });

    test('login with missing access token returns failure', () async {
      fakeEndpoints.onLogin = () => _loginResponse(includeAccessToken: false);

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage,
          'Invalid server response: missing access token');
      expect(result.user, isNull);
    });

    test('login with failed getMe returns failure and clears tokens', () async {
      fakeEndpoints.onLogin = () => _loginResponse();
      fakeEndpoints.onGetMe = () => throw Exception('User fetch failed');

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage, 'Failed to fetch user profile');
      final access = await tokenManager.getAccessToken();
      expect(access, isNull);
    });

    test('login with connection timeout returns "No internet connection"',
        () async {
      fakeEndpoints.onLogin = () => throw _dioException(
            type: DioExceptionType.connectionTimeout,
          );

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage, 'No internet connection');
    });

    test('login with connection error returns "No internet connection"',
        () async {
      fakeEndpoints.onLogin = () => throw _dioException(
            type: DioExceptionType.connectionError,
          );

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage, 'No internet connection');
    });

    test('login with 401 returns "Invalid email or password"', () async {
      fakeEndpoints.onLogin = () => throw _dioException(
            type: DioExceptionType.badResponse,
            statusCode: 401,
          );

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage, 'Invalid email or password');
    });

    test('login with 401 and detail string uses the detail message', () async {
      fakeEndpoints.onLogin = () => throw _dioException(
            type: DioExceptionType.badResponse,
            statusCode: 401,
            data: {'detail': 'Account locked'},
          );

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage, 'Account locked');
    });

    test('login with 503 returns service unavailable message', () async {
      fakeEndpoints.onLogin = () => throw _dioException(
            type: DioExceptionType.badResponse,
            statusCode: 503,
          );

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage,
          'Service unavailable. The backend is not running.');
    });

    test('login with 404 returns endpoint not found message', () async {
      fakeEndpoints.onLogin = () => throw _dioException(
            type: DioExceptionType.badResponse,
            statusCode: 404,
          );

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage,
          'Service endpoint not found. Please contact support.');
    });

    test('login with generic exception returns unexpected error', () async {
      fakeEndpoints.onLogin = () => throw Exception('Something went wrong');

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage, 'An unexpected error occurred');
    });

    test('login with 500+ status code returns server error message', () async {
      fakeEndpoints.onLogin = () => throw _dioException(
            type: DioExceptionType.badResponse,
            statusCode: 502,
          );

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage, contains('Server error'));
    });

    test('login with 401 and nested detail[detail] extracts inner message',
        () async {
      fakeEndpoints.onLogin = () => throw _dioException(
            type: DioExceptionType.badResponse,
            statusCode: 401,
            data: {'detail': {'detail': 'Session expired'}},
          );

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage, 'Session expired');
    });

    test('login with 401 and message field uses that message', () async {
      fakeEndpoints.onLogin = () => throw _dioException(
            type: DioExceptionType.badResponse,
            statusCode: 401,
            data: {'message': 'Custom auth error'},
          );

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage, 'Custom auth error');
    });

    test('login with 401 and error field uses that error', () async {
      fakeEndpoints.onLogin = () => throw _dioException(
            type: DioExceptionType.badResponse,
            statusCode: 401,
            data: {'error': 'unauthorized'},
          );

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage, 'unauthorized');
    });

    test('login with request cancelled returns cancellation message', () async {
      fakeEndpoints.onLogin = () => throw _dioException(
            type: DioExceptionType.cancel,
          );

      final result = await authService.login('test@test.com', 'password');

      expect(result.success, isFalse);
      expect(result.errorMessage, 'Request was cancelled');
    });

    // ── logout() ────────────────────────────────────────────────────────

    test('logout calls endpoint and clears tokens on success', () async {
      // First login
      fakeEndpoints.onLogin = () => _loginResponse();
      fakeEndpoints.onGetMe = () => _userResponse();
      await authService.login('test@test.com', 'password');

      bool logoutCalled = false;
      fakeEndpoints.onLogout = () {
        logoutCalled = true;
        return _defaultLogoutResponse();
      };

      await authService.logout();

      expect(logoutCalled, isTrue);
      final access = await tokenManager.getAccessToken();
      expect(access, isNull);
    });

    test('logout clears tokens even when server call fails', () async {
      // First login
      fakeEndpoints.onLogin = () => _loginResponse();
      fakeEndpoints.onGetMe = () => _userResponse();
      await authService.login('test@test.com', 'password');

      fakeEndpoints.onLogout = () => throw Exception('Server error');

      await authService.logout();

      final access = await tokenManager.getAccessToken();
      expect(access, isNull);
    });

    test('logout clears tokens even when server returns 500', () async {
      // First login
      fakeEndpoints.onLogin = () => _loginResponse();
      fakeEndpoints.onGetMe = () => _userResponse();
      await authService.login('test@test.com', 'password');

      fakeEndpoints.onLogout = () => throw _dioException(
            type: DioExceptionType.badResponse,
            statusCode: 500,
          );

      await authService.logout();

      final access = await tokenManager.getAccessToken();
      expect(access, isNull);
    });

    // ── getCurrentUser() ────────────────────────────────────────────────

    test('getCurrentUser returns user when getMe succeeds', () async {
      fakeEndpoints.onGetMe = () => _userResponse();

      final user = await authService.getCurrentUser();

      expect(user, isA<User>());
      expect(user!.email, 'test@test.com');
    });

    test('getCurrentUser returns null when getMe fails', () async {
      fakeEndpoints.onGetMe = () => throw Exception('fail');

      final user = await authService.getCurrentUser();

      expect(user, isNull);
    });

    test('getCurrentUser supports flat user response (no nested user key)',
        () async {
      fakeEndpoints.onGetMe = () => Response(
            requestOptions: RequestOptions(path: ''),
            data: {
              'id': 'u2',
              'email': 'flat@test.com',
              'fullName': 'Flat User',
              'role': 'dispatcher',
              'companyId': 'c2',
            },
            statusCode: 200,
          );

      final user = await authService.getCurrentUser();

      expect(user, isA<User>());
      expect(user!.email, 'flat@test.com');
    });

    test('getCurrentUser returns null when getMe returns non-map data',
        () async {
      fakeEndpoints.onGetMe = () => Response(
            requestOptions: RequestOptions(path: ''),
            data: 'not a map',
            statusCode: 200,
          );

      final user = await authService.getCurrentUser();

      expect(user, isNull);
    });

    // ── restoreSession() ────────────────────────────────────────────────

    test('restoreSession with no refresh token returns false', () async {
      final result = await authService.restoreSession();

      expect(result, isFalse);
    });

    test('restoreSession with empty refresh token returns false', () async {
      await tokenManager.saveTokens('at1', '');
      final result = await authService.restoreSession();

      expect(result, isFalse);
    });

    test('restoreSession with valid refresh returns true and tokens updated',
        () async {
      await tokenManager.saveTokens('at_old', 'rt_valid');

      fakeEndpoints.onRefresh = () => _refreshResponse(
            accessToken: 'at_new',
            refreshToken: 'rt_new',
          );
      fakeEndpoints.onGetMe = () => _userResponse();

      final result = await authService.restoreSession();

      expect(result, isTrue);
      final access = await tokenManager.getAccessToken();
      final refresh = await tokenManager.getRefreshToken();
      expect(access, 'at_new');
      expect(refresh, 'rt_new');
    });

    test(
        'restoreSession with failed refresh returns false and clears tokens',
        () async {
      await tokenManager.saveTokens('at1', 'rt1');

      fakeEndpoints.onRefresh = () => throw Exception('refresh failed');

      final result = await authService.restoreSession();

      expect(result, isFalse);
      final access = await tokenManager.getAccessToken();
      expect(access, isNull);
    });

    test(
        'restoreSession succeeds but getMe fails returns false and clears tokens',
        () async {
      await tokenManager.saveTokens('at1', 'rt1');

      fakeEndpoints.onRefresh = () => _refreshResponse(
            accessToken: 'at_new',
            refreshToken: 'rt_new',
          );
      fakeEndpoints.onGetMe = () => throw Exception('getMe failed');

      final result = await authService.restoreSession();

      expect(result, isFalse);
      final access = await tokenManager.getAccessToken();
      expect(access, isNull);
    });

    test('restoreSession with tryRefresh returning false clears tokens',
        () async {
      await tokenManager.saveTokens('at1', 'rt1');

      // Return no accessToken from refresh
      fakeEndpoints.onRefresh = () => _refreshResponse(includeAccessToken: false);

      final result = await authService.restoreSession();

      expect(result, isFalse);
      final access = await tokenManager.getAccessToken();
      expect(access, isNull);
    });

    // ── AuthResult constructor ──────────────────────────────────────────

    test('AuthResult can be created with only success', () {
      const result = AuthResult(success: true);
      expect(result.success, isTrue);
      expect(result.user, isNull);
      expect(result.errorMessage, isNull);
    });

    test('AuthResult can be created with error message', () {
      const result = AuthResult(
        success: false,
        errorMessage: 'Error',
      );
      expect(result.success, isFalse);
      expect(result.errorMessage, 'Error');
    });
  });
}

// ── Additional helpers ───────────────────────────────────────────────────────

Response _defaultLogoutResponse() => Response(
      requestOptions: RequestOptions(path: ''),
      data: {},
      statusCode: 200,
    );

Response _refreshResponse({
  bool includeAccessToken = true,
  bool includeRefreshToken = true,
  String? accessToken,
  String? refreshToken,
}) {
  final data = <String, dynamic>{};
  if (includeAccessToken) data['accessToken'] = accessToken ?? 'at_new';
  if (includeRefreshToken) data['refreshToken'] = refreshToken ?? 'rt_new';
  return Response(
    requestOptions: RequestOptions(path: ''),
    data: data,
    statusCode: 200,
  );
}
