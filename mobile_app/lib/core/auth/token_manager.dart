import '../network/endpoints/auth_endpoints.dart';
import '../network/message_bus.dart';
import '../storage/secure_token_store.dart';

/// Manages JWT token lifecycle including secure storage persistence,
/// automatic refresh, and in-memory token presence tracking.
///
/// Reads always delegate to [SecureTokenStore] to remain consistent with
/// any external clears (e.g. from the auth interceptor). The in-memory
/// `_hasTokens` flag is only used for the synchronous [isAuthenticated]
/// getter and is kept in sync by [saveTokens] / [clearTokens].
class TokenManager {
  final SecureTokenStore _store;
  final AuthEndpoints _endpoints;
  // ignore: unused_field
  final MessageBus _messageBus;

  bool _hasTokens = false;

  TokenManager(this._store, this._endpoints, this._messageBus);

  /// Loads the token-presence flag from secure storage.
  ///
  /// Call this once at app startup so that [isAuthenticated] returns the
  /// correct value without awaiting.
  Future<void> initialize() async {
    _hasTokens = await _store.hasTokens();
  }

  /// Returns the current access token from secure storage, or `null`.
  Future<String?> getAccessToken() => _store.getAccessToken();

  /// Returns the current refresh token from secure storage, or `null`.
  Future<String?> getRefreshToken() => _store.getRefreshToken();

  /// Persists both tokens to secure storage and marks the session as
  /// authenticated.
  Future<void> saveTokens(String access, String refresh) async {
    await _store.saveTokens(access, refresh);
    _hasTokens = true;
  }

  /// Removes all tokens from secure storage and marks the session as
  /// unauthenticated.
  ///
  /// Does **not** emit [ForceLogoutEvent] — that is the responsibility of
  /// the auth-interceptor's `onForceLogout` callback so that forced-logout
  /// and explicit-logout flows can be differentiated.
  Future<void> clearTokens() async {
    await _store.clearTokens();
    _hasTokens = false;
  }

  /// Attempts to exchange the current refresh token for a new token pair.
  ///
  /// Returns `true` if a new access token was obtained and persisted,
  /// `false` otherwise (e.g. refresh token expired or network error).
  Future<bool> tryRefresh() async {
    final refreshToken = await getRefreshToken();
    if (refreshToken == null || refreshToken.isEmpty) return false;

    try {
      final response = await _endpoints.refreshToken(refreshToken);
      final data = response.data as Map<String, dynamic>;

      final newAccess = data['accessToken'] as String?;
      final newRefresh = data['refreshToken'] as String?;

      if (newAccess != null) {
        await saveTokens(newAccess, newRefresh ?? refreshToken);
        return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  /// Whether the manager currently believes a valid session exists.
  ///
  /// This is a synchronous snapshot updated by [saveTokens] and
  /// [clearTokens]. For the authoritative answer use [getAccessToken].
  bool get isAuthenticated => _hasTokens;
}
