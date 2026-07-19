import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

/// Persistent, encrypted storage for authentication tokens.
///
/// Uses [FlutterSecureStorage] under the hood with platform-specific options:
/// - **Android**: `encryptedSharedPreferences: true`
/// - **iOS**: `accessibility: first_unlock_this_device`
class SecureTokenStore {
  final FlutterSecureStorage _storage;

  SecureTokenStore({FlutterSecureStorage? storage})
      : _storage = storage ?? FlutterSecureStorage(
          aOptions: const AndroidOptions(
            encryptedSharedPreferences: true,
          ),
          iOptions: const IOSOptions(
            accessibility: KeychainAccessibility.first_unlock_this_device,
          ),
        );

  static const _accessTokenKey = 'access_token';
  static const _refreshTokenKey = 'refresh_token';
  static const _deviceIdKey = 'operion_device_id';

  /// Persist both tokens.
  Future<void> saveTokens(String accessToken, String refreshToken) async {
    await Future.wait([
      _storage.write(key: _accessTokenKey, value: accessToken),
      _storage.write(key: _refreshTokenKey, value: refreshToken),
    ]);
  }

  /// Retrieve the stored access token, or `null` if none exists.
  Future<String?> getAccessToken() =>
      _storage.read(key: _accessTokenKey);

  /// Retrieve the stored refresh token, or `null` if none exists.
  Future<String?> getRefreshToken() =>
      _storage.read(key: _refreshTokenKey);

  /// Remove both tokens from secure storage.
  Future<void> clearTokens() async {
    await Future.wait([
      _storage.delete(key: _accessTokenKey),
      _storage.delete(key: _refreshTokenKey),
    ]);
  }

  /// Returns `true` if an access token is currently stored.
  Future<bool> hasTokens() async {
    final token = await _storage.read(key: _accessTokenKey);
    return token != null && token.isNotEmpty;
  }

  /// Retrieves or creates a persistent unique device identifier.
  ///
  /// The ID is generated once using UUID v4 on first access and stored
  /// securely so it survives app restarts and reinstalls (as long as
  /// secure storage is not wiped).
  Future<String> getOrCreateDeviceId() async {
    var id = await _storage.read(key: _deviceIdKey);
    if (id == null || id.isEmpty) {
      id = const Uuid().v4();
      await _storage.write(key: _deviceIdKey, value: id);
    }
    return id;
  }
}
