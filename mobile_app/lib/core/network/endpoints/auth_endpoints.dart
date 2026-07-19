import 'package:dio/dio.dart';

import '../api_client.dart';

/// Endpoint methods for authentication.
class AuthEndpoints {
  final ApiClient client;

  AuthEndpoints(this.client);

  static const loginPath = '/api/v1/auth/token';
  static const refreshPath = '/api/v1/auth/refresh';
  static const logoutPath = '/api/v1/auth/logout';
  static const mePath = '/api/v1/auth/me';

  /// Authenticate with [email] and [password].
  ///
  /// When [deviceId] is provided it is included in the form body so the
  /// server can associate the login with a specific device.
  Future<Response> login(String email, String password, {String? deviceId}) {
    final data = <String, dynamic>{
      'username': email,
      'password': password,
    };
    if (deviceId != null && deviceId.isNotEmpty) {
      data['device_id'] = deviceId;
    }
    return client.dio.post(
      loginPath,
      data: data,
      options: Options(contentType: Headers.formUrlEncodedContentType),
    );
  }

  /// Exchange a valid [refreshToken] for a new access token.
  Future<Response> refreshToken(String refreshToken) =>
      client.post(refreshPath, data: {'refresh_token': refreshToken});

  /// Invalidate the current session.
  Future<Response> logout() => client.post(logoutPath);

  /// Fetch the currently authenticated user's profile.
  Future<Response> getMe() => client.get(mePath);

  /// Register this device with the backend after a successful login.
  ///
  /// [deviceId] is the persistent device UUID.
  /// [platform] should be `"android"` or `"ios"`.
  /// [deviceName] is an optional human-readable device label.
  /// [fcmToken] is the optional Firebase Cloud Messaging registration token.
  Future<Response> registerDevice({
    required String deviceId,
    required String platform,
    String? deviceName,
    String? fcmToken,
  }) =>
      client.post('/api/v1/mobile/devices/register', data: {
        'device_id': deviceId,
        'platform': platform,
        if (deviceName != null) 'device_name': deviceName,
        if (fcmToken != null) 'token': fcmToken,
      });
}
