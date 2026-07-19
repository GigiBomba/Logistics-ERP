import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/network/auth_interceptor.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/// Dio with [AuthInterceptor] and a capturing interceptor that resolves all
/// requests with 200. Used for onRequest (Authorization header) tests.
Dio _createResolvingDio({
  required AuthInterceptor authInterceptor,
  required _CapturingInterceptor capture,
}) {
  final dio = Dio(BaseOptions(baseUrl: 'https://api.test.com'));
  dio.interceptors.clear();
  dio.interceptors.add(authInterceptor);
  dio.interceptors.add(capture);
  dio.interceptors.add(_ResolvingInterceptor());
  return dio;
}

/// A mock interceptor that captures request options after the AuthInterceptor.
class _CapturingInterceptor extends Interceptor {
  final List<RequestOptions> capturedRequests = [];

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    capturedRequests.add(options);
    handler.next(options);
  }
}

/// Resolves every request with 200.
class _ResolvingInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    handler.resolve(Response(
      requestOptions: options,
      data: {'status': 'ok'},
      statusCode: 200,
    ));
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  group('AuthInterceptor', () {
    String? currentAccessToken;
    String? currentRefreshToken;
    String? savedAccess;
    String? savedRefresh;
    bool tokensCleared = false;
    bool forceLogoutCalled = false;

    late AuthInterceptor interceptor;
    late _CapturingInterceptor capture;

    setUp(() {
      currentAccessToken = null;
      currentRefreshToken = null;
      savedAccess = null;
      savedRefresh = null;
      tokensCleared = false;
      forceLogoutCalled = false;

      interceptor = AuthInterceptor(
        getAccessToken: () async => currentAccessToken,
        getRefreshToken: () async => currentRefreshToken,
        saveTokens: (access, refresh) async {
          savedAccess = access;
          savedRefresh = refresh;
        },
        clearTokens: () async {
          tokensCleared = true;
        },
        onForceLogout: () {
          forceLogoutCalled = true;
        },
      );

      capture = _CapturingInterceptor();
    });

    // ── onRequest – Authorization header ────────────────────────────────

    test('adds Authorization header to non-public endpoints', () async {
      currentAccessToken = 'valid_token';
      final dio = _createResolvingDio(
        authInterceptor: interceptor,
        capture: capture,
      );

      await dio.get('/api/v1/transports');

      expect(capture.capturedRequests, hasLength(1));
      final req = capture.capturedRequests.first;
      expect(req.headers['Authorization'], 'Bearer valid_token');
    });

    test('does NOT add Authorization to login endpoint', () async {
      currentAccessToken = 'valid_token';
      final dio = _createResolvingDio(
        authInterceptor: interceptor,
        capture: capture,
      );

      await dio.post('/api/v1/auth/token');

      expect(capture.capturedRequests, hasLength(1));
      final req = capture.capturedRequests.first;
      expect(req.headers['Authorization'], isNull);
    });

    test('does NOT add Authorization to refresh endpoint', () async {
      currentAccessToken = 'valid_token';
      final dio = _createResolvingDio(
        authInterceptor: interceptor,
        capture: capture,
      );

      await dio.post('/api/v1/auth/refresh');

      expect(capture.capturedRequests, hasLength(1));
      final req = capture.capturedRequests.first;
      expect(req.headers['Authorization'], isNull);
    });

    test('does NOT add Authorization when no token is available', () async {
      currentAccessToken = null;
      final dio = _createResolvingDio(
        authInterceptor: interceptor,
        capture: capture,
      );

      await dio.get('/api/v1/transports');

      expect(capture.capturedRequests, hasLength(1));
      final req = capture.capturedRequests.first;
      expect(req.headers['Authorization'], isNull);
    });

    test('does NOT add Authorization for empty token', () async {
      currentAccessToken = '';
      final dio = _createResolvingDio(
        authInterceptor: interceptor,
        capture: capture,
      );

      await dio.get('/api/v1/transports');

      expect(capture.capturedRequests, hasLength(1));
      final req = capture.capturedRequests.first;
      expect(req.headers['Authorization'], isNull);
    });

    test('handles full URL paths for public endpoint detection', () async {
      currentAccessToken = 'valid_token';
      final dio = _createResolvingDio(
        authInterceptor: interceptor,
        capture: capture,
      );

      await dio.post(
          'https://api.test.com/api/v1/auth/refresh');

      expect(capture.capturedRequests, hasLength(1));
      final req = capture.capturedRequests.first;
      expect(req.headers['Authorization'], isNull);
    });

    // ── onError – direct tests ─────────────────────────────────────────

    test(
        'handles non-401 errors without calling refresh or force logout',
        () async {
      final error = _dioError(
        path: '/api/v1/transports',
        statusCode: 500,
      );

      final handler = _TestErrorHandler();
      interceptor.onError(error, handler);
      await Future(() {});

      expect(tokensCleared, isFalse);
      expect(forceLogoutCalled, isFalse);
    });

    test('handles 403 errors without calling refresh or force logout',
        () async {
      final error = _dioError(
        path: '/api/v1/transports',
        statusCode: 403,
      );

      final handler = _TestErrorHandler();
      interceptor.onError(error, handler);
      await Future(() {});

      expect(tokensCleared, isFalse);
      expect(forceLogoutCalled, isFalse);
    });

    test('401 without refresh callbacks forwards error without forceLogout',
        () async {
      final minimalInterceptor = AuthInterceptor(
        getAccessToken: () async => 'token',
      );

      final error = _dioError(
        path: '/api/v1/transports',
        statusCode: 401,
      );

      final handler = _TestErrorHandler();
      minimalInterceptor.onError(error, handler);
      await Future(() {});

      // Without refresh callbacks, the error is just forwarded
      expect(forceLogoutCalled, isFalse);
    });

    test('401 with null refresh token triggers force logout', () async {
      currentRefreshToken = null;

      final error = _dioError(
        path: '/api/v1/transports',
        statusCode: 401,
      );

      final handler = _TestErrorHandler();
      interceptor.onError(error, handler);
      await Future(() {});
      await Future(() {});

      expect(forceLogoutCalled, isTrue);
      expect(tokensCleared, isTrue);
    });

    test('401 with empty refresh token triggers force logout', () async {
      currentRefreshToken = '';

      final error = _dioError(
        path: '/api/v1/transports',
        statusCode: 401,
      );

      final handler = _TestErrorHandler();
      interceptor.onError(error, handler);
      await Future(() {});
      await Future(() {});

      expect(forceLogoutCalled, isTrue);
      expect(tokensCleared, isTrue);
    });

    test('401 on refresh endpoint is not retried or force-logged', () async {
      // When the failing request itself IS the refresh endpoint,
      // the interceptor forwards the error without attempting another
      // refresh or triggering a force-logout.
      final error = _dioError(
        path: '/api/v1/auth/refresh',
        statusCode: 401,
      );

      final handler = _TestErrorHandler();
      interceptor.onError(error, handler);
      await Future(() {});
      await Future(() {});

      // The interceptor should NOT call force-logout; it just forwards.
      expect(forceLogoutCalled, isFalse);
      expect(tokensCleared, isFalse);
    });

    test('401 with valid refresh token attempts refresh and fails gracefully',
        () async {
      currentRefreshToken = 'valid_rt';

      final error = _dioError(
        path: '/api/v1/transports',
        statusCode: 401,
      );

      final handler = _TestErrorHandler();
      interceptor.onError(error, handler);

      // Allow async onError to complete (includes failed network call)
      for (int i = 0; i < 10; i++) {
        await Future(() {});
      }

      // The refresh call will fail (no network), so force-logout should fire.
      expect(forceLogoutCalled, isTrue);
      expect(tokensCleared, isTrue);
    });

    // ── Edge cases ────────────────────────────────────────────────────

    test('handle non-standard path format for public detection', () async {
      final i = AuthInterceptor(getAccessToken: () async => 'token');

      expect(
        () => i.onRequest(
          RequestOptions(path: '/api/v1/auth/token'),
          _MockRequestHandler(),
        ),
        returnsNormally,
      );
    });

    test('normalisePath handles bad URI gracefully', () async {
      final i = AuthInterceptor(getAccessToken: () async => 'token');

      expect(
        () => i.onRequest(
          RequestOptions(path: ':::invalid uri'),
          _MockRequestHandler(),
        ),
        returnsNormally,
      );
    });

    test('forceLogout handles null clearTokens and onForceLogout', () async {
      final i = AuthInterceptor(
        getAccessToken: () async => 'token',
        getRefreshToken: () async => 'rt',
        saveTokens: (a, r) async {},
      );

      final error = _dioError(
        path: '/api/v1/test',
        statusCode: 401,
      );

      final handler = _TestErrorHandler();
      i.onError(error, handler);
      await Future(() {});
      // No crash expected
    });

    test('VoidCallback typedef compiles', () {
      // Verify the typedef from auth_interceptor.dart is accessible
      expect(VoidCallback, isNotNull);
    });
  });
}

// ── Helpers ─────────────────────────────────────────────────────────────────

DioException _dioError({
  required String path,
  required int statusCode,
}) {
  return DioException(
    requestOptions: RequestOptions(path: path),
    type: DioExceptionType.badResponse,
    response: Response(
      requestOptions: RequestOptions(path: path),
      statusCode: statusCode,
      data: {},
    ),
  );
}

class _MockRequestHandler extends RequestInterceptorHandler {
  @override
  void next(RequestOptions options) {}

  @override
  void resolve(Response<dynamic> response, [bool? callFollowingResponse]) {}

  @override
  void reject(DioException error, [bool? callFollowingError]) {}
}

class _TestErrorHandler extends ErrorInterceptorHandler {
  @override
  void next(DioException err) {}

  @override
  void resolve(Response<dynamic> response, [bool? callFollowingResponse]) {}

  @override
  void reject(DioException error, [bool? callFollowingError]) {}
}
