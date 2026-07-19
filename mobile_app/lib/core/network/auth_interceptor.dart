import 'dart:async';
import 'dart:developer' as developer;

import 'package:dio/dio.dart';

/// Interceptor that attaches an Authorization header to every request and
/// handles 401 responses by attempting a token refresh.
///
/// When a 401 is received:
/// 1. The refresh token is fetched via [getRefreshToken].
/// 2. A POST is made to `/api/v1/auth/refresh` with that token.
/// 3. The new tokens are persisted via [saveTokens].
/// 4. The original request is retried with the new access token.
///
/// If the refresh itself fails, [clearTokens] and [onForceLogout] are called,
/// and the original error is forwarded.
class AuthInterceptor extends QueuedInterceptor {
  final Future<String?> Function() getAccessToken;
  final Future<String?> Function()? getRefreshToken;
  final Future<void> Function(String access, String refresh)? saveTokens;
  final Future<void> Function()? clearTokens;
  final VoidCallback? onForceLogout;

  /// Endpoints that should never carry an Authorization header.
  static const _publicEndpoints = <String>{
    '/api/v1/auth/token',
    '/api/v1/auth/refresh',
  };

  AuthInterceptor({
    required this.getAccessToken,
    this.getRefreshToken,
    this.saveTokens,
    this.clearTokens,
    this.onForceLogout,
  });

  /// Whether [path] is a public endpoint that does not require auth.
  bool _isPublic(String path) {
    // Strip base URL prefix if present (e.g. "https://api.example.com/api/v1/auth/token")
    final normalized = _normalisePath(path);
    return _publicEndpoints.any((e) => normalized.endsWith(e));
  }

  String _normalisePath(String path) {
    try {
      final uri = Uri.parse(path);
      return uri.path;
    } on FormatException {
      return path;
    }
  }

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (!_isPublic(options.path)) {
      final token = await getAccessToken();
      if (token != null && token.isNotEmpty) {
        options.headers['Authorization'] = 'Bearer $token';
      }
    }
    handler.next(options);
  }

  @override
  void onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    // Only attempt refresh on 401 and when a refresh-token callback is provided.
    if (err.response?.statusCode != 401 ||
        getRefreshToken == null ||
        saveTokens == null) {
      return handler.next(err);
    }

    // Don't retry if the failing request was itself the refresh call.
    final path = _normalisePath(err.requestOptions.path);
    if (path.endsWith('/api/v1/auth/refresh')) {
      return handler.next(err);
    }

    try {
      final refreshToken = await getRefreshToken?.call();
      if (refreshToken == null || refreshToken.isEmpty) {
        return _forceLogout(err, handler);
      }

      // Attempt token refresh
      final refreshDio = Dio(BaseOptions(
        baseUrl: err.requestOptions.baseUrl,
        headers: {'Content-Type': 'application/json'},
      ));
      final refreshResponse = await refreshDio.post(
        '/api/v1/auth/refresh',
        data: {'refresh_token': refreshToken},
      );

      if (refreshResponse.statusCode == 200) {
        final data = refreshResponse.data is Map<String, dynamic>
            ? refreshResponse.data as Map<String, dynamic>
            : <String, dynamic>{};
        final newAccess = data['access_token'] as String?;
        final newRefresh = data['refresh_token'] as String?;

        if (newAccess != null) {
          await saveTokens!(newAccess, newRefresh ?? refreshToken);

          // Retry the original request with the new token
          err.requestOptions.headers['Authorization'] = 'Bearer $newAccess';
          final response = await Dio(BaseOptions(
            baseUrl: err.requestOptions.baseUrl,
          )).fetch(err.requestOptions);
          return handler.resolve(response);
        }
      }

      // Refresh response was not 200 – force logout
      return _forceLogout(err, handler);
    } catch (e) {
      developer.log('AuthInterceptor: refresh failed – $e', name: 'AuthInterceptor');
      return _forceLogout(err, handler);
    }
  }

  void _forceLogout(
    DioException err,
    ErrorInterceptorHandler handler,
  ) {
    clearTokens?.call();
    onForceLogout?.call();
    handler.next(err);
  }
}

typedef VoidCallback = void Function();
