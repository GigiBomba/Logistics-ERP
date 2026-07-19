import 'package:dio/dio.dart';

import 'auth_interceptor.dart';

/// Singleton Dio-based HTTP client for the Operion Mobile app.
///
/// Create an instance via [ApiClient.create] which wires up:
/// - Base URL and sensible timeouts
/// - JSON content-type header
/// - A [LogInterceptor] for debug logging
/// - The [AuthInterceptor] for automatic token management
///
/// Convenience methods ([get], [post], [put], [patch], [delete], [upload])
/// delegate directly to the underlying [Dio] instance.
class ApiClient {
  final Dio dio;

  ApiClient._(this.dio);

  /// Creates a fully-configured [ApiClient].
  ///
  /// [baseUrl] is the root URL of the Operion API.
  /// [getAccessToken] is invoked by the auth interceptor before every
  /// non-public request to obtain the current Bearer token.
  static ApiClient create({
    required String baseUrl,
    required Future<String?> Function() getAccessToken,
    Future<String?> Function()? getRefreshToken,
    Future<void> Function(String access, String refresh)? saveTokens,
    Future<void> Function()? clearTokens,
    VoidCallback? onForceLogout,
    String? apiKey,
  }) {
    final headers = <String, dynamic>{'Content-Type': 'application/json'};
    if (apiKey != null && apiKey.isNotEmpty) {
      headers['X-API-Key'] = apiKey;
    }

    final dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 30),
      headers: headers,
    ));

    // ── Logging interceptor ─────────────────────
    dio.interceptors.add(LogInterceptor(
      requestBody: true,
      responseBody: true,
      logPrint: (obj) => print('[Dio] $obj'),
    ));

    // ── Auth interceptor ────────────────────────
    dio.interceptors.add(AuthInterceptor(
      getAccessToken: getAccessToken,
      getRefreshToken: getRefreshToken,
      saveTokens: saveTokens,
      clearTokens: clearTokens,
      onForceLogout: onForceLogout,
    ));

    return ApiClient._(dio);
  }

  // ── Convenience methods ───────────────────────

  /// Sends a GET request to the given [path].
  Future<Response<T>> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) =>
      dio.get<T>(path, queryParameters: queryParameters);

  /// Sends a POST request to the given [path] with optional [data].
  Future<Response<T>> post<T>(
    String path, {
    dynamic data,
  }) =>
      dio.post<T>(path, data: data);

  /// Sends a PUT request to the given [path] with optional [data].
  Future<Response<T>> put<T>(
    String path, {
    dynamic data,
  }) =>
      dio.put<T>(path, data: data);

  /// Sends a PATCH request to the given [path] with optional [data].
  Future<Response<T>> patch<T>(
    String path, {
    dynamic data,
  }) =>
      dio.patch<T>(path, data: data);

  /// Sends a DELETE request to the given [path].
  Future<Response<T>> delete<T>(String path) => dio.delete<T>(path);

  /// Uploads a [FormData] payload (e.g. file uploads) to [path].
  Future<Response<T>> upload<T>(
    String path,
    FormData formData,
  ) =>
      dio.post<T>(
        path,
        data: formData,
        options: Options(contentType: 'multipart/form-data'),
      );
}
