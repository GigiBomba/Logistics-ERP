import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';

/// Shared in-memory [SecureTokenStore] fake for widget tests.
///
/// Defaults to an empty store (`hasTokens == false`). Pass
/// [initialAccessToken] / [initialRefreshToken] to simulate a
/// pre-authenticated session.
class MockSecureTokenStore extends SecureTokenStore {
  String? _accessToken;
  String? _refreshToken;

  MockSecureTokenStore({
    String? initialAccessToken,
    String? initialRefreshToken,
  })  : _accessToken = initialAccessToken,
        _refreshToken = initialRefreshToken;

  @override
  Future<bool> hasTokens() async => _accessToken != null;

  @override
  Future<String?> getAccessToken() async => _accessToken;

  @override
  Future<String?> getRefreshToken() async => _refreshToken;

  @override
  Future<void> saveTokens(String access, String refresh) async {
    _accessToken = access;
    _refreshToken = refresh;
  }

  @override
  Future<void> clearTokens() async {
    _accessToken = null;
    _refreshToken = null;
  }
}

/// Shared [BiometricService] fake that reports biometrics as unavailable and
/// never authenticates successfully.
class MockBiometricService extends BiometricService {
  @override
  Future<bool> isAvailable() async => false;

  @override
  Future<bool> authenticate({required String reason}) async => false;
}