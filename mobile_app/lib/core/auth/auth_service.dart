import 'dart:developer' as developer;
import 'dart:io' show Platform;

import 'package:dio/dio.dart';

import '../../shared/models/user.dart';
import '../network/endpoints/auth_endpoints.dart';
import '../storage/secure_token_store.dart';
import 'token_manager.dart';

/// The result of an authentication attempt.
class AuthResult {
  /// Whether authentication succeeded.
  final bool success;

  /// The authenticated [User] profile, present only when [success] is true.
  final User? user;

  /// A human-readable error description, present only when [success] is
  /// false.
  final String? errorMessage;

  const AuthResult({
    required this.success,
    this.user,
    this.errorMessage,
  });
}

/// High-level authentication service that orchestrates login, logout,
/// session restoration, and current-user retrieval.
class AuthService {
  final AuthEndpoints _endpoints;
  final TokenManager _tokenManager;
  final SecureTokenStore _tokenStore;

  AuthService(this._endpoints, this._tokenManager, this._tokenStore);

  /// Authenticates with the given [email] and [password].
  ///
  /// On success tokens are persisted via [_tokenManager] and the [User]
  /// profile is fetched from the server. A persistent device identifier is
  /// included in the login request and the device is registered with the
  /// backend afterwards. Returns an [AuthResult] with the outcome.
  Future<AuthResult> login(String email, String password) async {
    try {
      final deviceId = await _tokenStore.getOrCreateDeviceId();
      final response = await _endpoints.login(
        email,
        password,
        deviceId: deviceId,
      );
      final responseData = response.data;
      if (responseData is! Map<String, dynamic>) {
        return const AuthResult(
          success: false,
          errorMessage: 'Unexpected server response format',
        );
      }
      final data = responseData;

      final accessToken = (data['accessToken'] as String?) ??
          (data['access_token'] as String?);
      final refreshToken = (data['refreshToken'] as String?) ??
          (data['refresh_token'] as String?);

      if (accessToken == null) {
        return const AuthResult(
          success: false,
          errorMessage: 'Invalid server response: missing access token',
        );
      }

      await _tokenManager.saveTokens(accessToken, refreshToken ?? '');

      final user = await _fetchCurrentUser();
      if (user == null) {
        await _tokenManager.clearTokens();
        return const AuthResult(
          success: false,
          errorMessage: 'Failed to fetch user profile',
        );
      }

      // Register the device with the backend (best-effort).
      await _registerDevice(deviceId);

      return AuthResult(success: true, user: user);
    } on DioException catch (e) {
      return AuthResult(
        success: false,
        errorMessage: _mapDioError(e),
      );
    } catch (e) {
      return const AuthResult(
        success: false,
        errorMessage: 'An unexpected error occurred',
      );
    }
  }

  /// Logs out by calling the logout endpoint (best-effort) and clearing all
  /// persisted tokens.
  ///
  /// The caller is responsible for updating the auth state to
  /// [AuthState.unauthenticated] after this completes.
  Future<void> logout() async {
    try {
      await _endpoints.logout();
    } catch (_) {
      // Swallow — we always want to clear local state even if the server
      // call fails.
    }
    await _tokenManager.clearTokens();
  }

  /// Fetches the currently authenticated user's profile from the `/me`
  /// endpoint. Returns `null` if the request fails.
  Future<User?> getCurrentUser() => _fetchCurrentUser();

  /// Attempts to restore a previous session by refreshing the stored refresh
  /// token. Returns `true` if the session was restored and a fresh [User]
  /// profile was fetched.
  Future<bool> restoreSession() async {
    final refreshToken = await _tokenManager.getRefreshToken();
    if (refreshToken == null || refreshToken.isEmpty) return false;

    final refreshed = await _tokenManager.tryRefresh();
    if (!refreshed) {
      await _tokenManager.clearTokens();
      return false;
    }

    try {
      final user = await _fetchCurrentUser();
      if (user == null) {
        await _tokenManager.clearTokens();
        return false;
      }
      return true;
    } catch (_) {
      await _tokenManager.clearTokens();
      return false;
    }
  }

  // ── Private helpers ──────────────────────────────────────────────────

  /// Registers the device with the backend after a successful login.
  ///
  /// This is a best-effort call — failures are silently swallowed so they
  /// never block the login flow.
  Future<void> _registerDevice(String deviceId) async {
    try {
      final platform = Platform.isAndroid ? 'android' : 'ios';
      await _endpoints.registerDevice(
        deviceId: deviceId,
        platform: platform,
        deviceName: Platform.localHostname,
      );
    } catch (_) {
      // Best-effort only.
    }
  }

  Future<User?> _fetchCurrentUser() async {
    try {
      final response = await _endpoints.getMe();
      final data = response.data as Map<String, dynamic>;
      // Support both nested `{ user: { ... } }` and flat `{ id, email, ... }`
      final rawUser = data['user'];
      final userData = rawUser is Map<String, dynamic> ? rawUser : data;
      return User.fromJson(userData);
    } on DioException catch (e) {
      developer.log(
        '_fetchCurrentUser DioException: type=${e.type} '
        'status=${e.response?.statusCode} body=${e.response?.data}',
        name: 'AuthService',
      );
      return null;
    } catch (e, s) {
      developer.log(
        '_fetchCurrentUser error: $e\n$s',
        name: 'AuthService',
      );
      return null;
    }
  }

  String _mapDioError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.connectionError:
        return 'No internet connection';
      case DioExceptionType.badResponse:
        final statusCode = e.response?.statusCode;
        if (statusCode == 503) {
          return 'Service unavailable. The backend is not running.';
        }
        if (statusCode == 404) {
          return 'Service endpoint not found. Please contact support.';
        }
        if (statusCode == 401) {
          final body = e.response?.data;
          if (body is Map<String, dynamic>) {
            // Try common error-field patterns
            final detail = body['detail'];
            if (detail is Map<String, dynamic>) {
              return (detail['detail'] as String?) ?? 'Invalid email or password';
            }
            if (detail is String) return detail;
            final message = body['message'];
            if (message is String) return message;
            final error = body['error'];
            if (error is String) return error;
          }
          return 'Invalid email or password';
        }
        if (statusCode != null && statusCode >= 500) {
          return 'Server error (${e.response?.statusCode}). The backend may be down or requires a database migration.';
        }
        final body = e.response?.data;
        if (body is Map<String, dynamic>) {
          return (body['message'] as String?) ?? 'An error occurred';
        }
        return 'An error occurred';
      case DioExceptionType.cancel:
        return 'Request was cancelled';
      default:
        return 'An unexpected error occurred';
    }
  }
}
