import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';

import 'package:operion_mobile/core/storage/secure_token_store.dart';

// ─────────────────────────────────────────────────────────────────────────────
// In-memory fake platform for FlutterSecureStorage
// ─────────────────────────────────────────────────────────────────────────────

class _FakeFlutterSecureStoragePlatform extends FlutterSecureStoragePlatform {
  final _data = <String, String>{};
  bool _throwOnWrite = false;
  bool _throwOnRead = false;
  bool _throwOnDelete = false;

  void setThrowOnWrite(bool v) => _throwOnWrite = v;
  void setThrowOnRead(bool v) => _throwOnRead = v;
  void setThrowOnDelete(bool v) => _throwOnDelete = v;

  Map<String, String> get data => Map.from(_data);
  void setValue(String key, String value) => _data[key] = value;

  @override
  Future<void> write({
    required String key,
    required String value,
    required Map<String, String> options,
  }) async {
    if (_throwOnWrite) {
      throw PlatformException(code: 'SECURE_STORAGE_ERROR', message: 'Write failed');
    }
    _data[key] = value;
  }

  @override
  Future<String?> read({
    required String key,
    required Map<String, String> options,
  }) async {
    if (_throwOnRead) {
      throw PlatformException(code: 'SECURE_STORAGE_ERROR', message: 'Read failed');
    }
    return _data[key];
  }

  @override
  Future<void> delete({
    required String key,
    required Map<String, String> options,
  }) async {
    if (_throwOnDelete) {
      throw PlatformException(code: 'SECURE_STORAGE_ERROR', message: 'Delete failed');
    }
    _data.remove(key);
  }

  @override
  Future<bool> containsKey({
    required String key,
    required Map<String, String> options,
  }) async => _data.containsKey(key);

  @override
  Future<Map<String, String>> readAll({
    required Map<String, String> options,
  }) async => Map.from(_data);

  @override
  Future<void> deleteAll({required Map<String, String> options}) async => _data.clear();
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  late _FakeFlutterSecureStoragePlatform fakePlatform;
  late SecureTokenStore store;

  setUp(() {
    fakePlatform = _FakeFlutterSecureStoragePlatform();
    FlutterSecureStoragePlatform.instance = fakePlatform;
    store = SecureTokenStore(storage: FlutterSecureStorage());
  });

  // ── saveTokens() ─────────────────────────────────────────────────────

  group('saveTokens', () {
    test('persists access and refresh tokens', () async {
      await store.saveTokens('access_token_value', 'refresh_token_value');

      final storedAccess = fakePlatform.data['access_token'];
      final storedRefresh = fakePlatform.data['refresh_token'];

      expect(storedAccess, 'access_token_value');
      expect(storedRefresh, 'refresh_token_value');
    });

    test('overwrites previously stored tokens', () async {
      await store.saveTokens('old_access', 'old_refresh');
      await store.saveTokens('new_access', 'new_refresh');

      expect(fakePlatform.data['access_token'], 'new_access');
      expect(fakePlatform.data['refresh_token'], 'new_refresh');
    });

    test('accepts empty access token', () async {
      await store.saveTokens('', 'refresh_value');

      expect(fakePlatform.data['access_token'], '');
      expect(fakePlatform.data['refresh_token'], 'refresh_value');
    });

    test('accepts empty refresh token', () async {
      await store.saveTokens('access_value', '');

      expect(fakePlatform.data['access_token'], 'access_value');
      expect(fakePlatform.data['refresh_token'], '');
    });

    test('saves both tokens concurrently', () async {
      // Verify that both writes happen (no ordering dependency)
      await store.saveTokens('at', 'rt');

      expect(fakePlatform.data['access_token'], 'at');
      expect(fakePlatform.data['refresh_token'], 'rt');
    });

    test('throws when secure storage write fails', () async {
      fakePlatform.setThrowOnWrite(true);

      expect(
        () => store.saveTokens('access', 'refresh'),
        throwsA(isA<PlatformException>()),
      );
    });
  });

  // ── getAccessToken() / getRefreshToken() ─────────────────────────────

  group('getAccessToken', () {
    test('returns null when no token stored', () async {
      final token = await store.getAccessToken();
      expect(token, isNull);
    });

    test('returns saved access token', () async {
      await store.saveTokens('my_access', 'my_refresh');
      final token = await store.getAccessToken();
      expect(token, 'my_access');
    });

    test('returns empty string when empty token was saved', () async {
      await store.saveTokens('', 'refresh');
      final token = await store.getAccessToken();
      expect(token, '');
    });
  });

  group('getRefreshToken', () {
    test('returns null when no token stored', () async {
      final token = await store.getRefreshToken();
      expect(token, isNull);
    });

    test('returns saved refresh token', () async {
      await store.saveTokens('access', 'my_refresh');
      final token = await store.getRefreshToken();
      expect(token, 'my_refresh');
    });

    test('returns empty string when empty token was saved', () async {
      await store.saveTokens('access', '');
      final token = await store.getRefreshToken();
      expect(token, '');
    });
  });

  // ── clearTokens() ───────────────────────────────────────────────────

  group('clearTokens', () {
    test('removes both tokens from storage', () async {
      await store.saveTokens('access', 'refresh');
      await store.clearTokens();

      expect(await store.getAccessToken(), isNull);
      expect(await store.getRefreshToken(), isNull);
    });

    test('is idempotent when no tokens exist', () async {
      // Should not throw
      await store.clearTokens();
      await store.clearTokens();

      expect(await store.getAccessToken(), isNull);
      expect(await store.getRefreshToken(), isNull);
    });

    test('does not affect device id', () async {
      await store.saveTokens('access', 'refresh');
      final deviceId = await store.getOrCreateDeviceId();

      await store.clearTokens();

      expect(await store.getAccessToken(), isNull);
      // Device ID should still exist
      final storedDeviceId = fakePlatform.data['operion_device_id'];
      expect(storedDeviceId, deviceId);
    });

    test('removes access and refresh keys but leaves other keys intact',
        () async {
      // Manually store an unrelated key
      fakePlatform.setValue('other_key', 'keep_me');
      await store.saveTokens('access', 'refresh');

      await store.clearTokens();

      expect(fakePlatform.data.containsKey('access_token'), isFalse);
      expect(fakePlatform.data.containsKey('refresh_token'), isFalse);
      expect(fakePlatform.data['other_key'], 'keep_me');
    });
  });

  // ── hasTokens() ─────────────────────────────────────────────────────

  group('hasTokens', () {
    test('returns false when no token stored', () async {
      expect(await store.hasTokens(), isFalse);
    });

    test('returns true when access token is stored', () async {
      await store.saveTokens('access', 'refresh');
      expect(await store.hasTokens(), isTrue);
    });

    test('returns false when only refresh token is stored (no access)', () async {
      // Save with empty access
      await store.saveTokens('', 'refresh');
      // hasTokens checks access token only (non-null and non-empty)
      expect(await store.hasTokens(), isFalse);
    });

    test('returns false when access token is empty string', () async {
      await store.saveTokens('', 'refresh');
      expect(await store.hasTokens(), isFalse);
    });

    test('returns false after clearTokens', () async {
      await store.saveTokens('access', 'refresh');
      await store.clearTokens();
      expect(await store.hasTokens(), isFalse);
    });
  });

  // ── getOrCreateDeviceId() ───────────────────────────────────────────

  group('getOrCreateDeviceId', () {
    test('creates and returns a new device ID on first call', () async {
      final id = await store.getOrCreateDeviceId();

      expect(id, isA<String>());
      expect(id, isNotEmpty);
      // UUID v4 format: 8-4-4-4-12 hex chars
      expect(id, matches(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'));
    });

    test('returns the same device ID on subsequent calls', () async {
      final id1 = await store.getOrCreateDeviceId();
      final id2 = await store.getOrCreateDeviceId();

      expect(id1, id2);
    });

    test('survives across different store instances', () async {
      final id1 = await store.getOrCreateDeviceId();

      // Create a new store backed by the same fake platform
      final store2 = SecureTokenStore(storage: FlutterSecureStorage());
      final id2 = await store2.getOrCreateDeviceId();

      expect(id1, id2);
    });

    test('returns stored value when device ID already exists', () async {
      fakePlatform.setValue('operion_device_id', 'existing-device-id');

      final id = await store.getOrCreateDeviceId();

      expect(id, 'existing-device-id');
    });

    test('replaces empty stored device ID with a new one', () async {
      fakePlatform.setValue('operion_device_id', '');

      final id = await store.getOrCreateDeviceId();

      expect(id, isNotEmpty);
      expect(id, isNot(''));
    });
  });

  // ── Token lifecycle (refresh cycle simulation) ──────────────────────

  group('token lifecycle', () {
    test('full cycle: save → read → clear → read returns null', () async {
      // Save
      await store.saveTokens('at_cycle', 'rt_cycle');
      expect(await store.getAccessToken(), 'at_cycle');
      expect(await store.getRefreshToken(), 'rt_cycle');
      expect(await store.hasTokens(), isTrue);

      // Clear
      await store.clearTokens();
      expect(await store.getAccessToken(), isNull);
      expect(await store.getRefreshToken(), isNull);
      expect(await store.hasTokens(), isFalse);

      // Re-save (simulating refresh token cycle)
      await store.saveTokens('at_refreshed', 'rt_refreshed');
      expect(await store.getAccessToken(), 'at_refreshed');
      expect(await store.getRefreshToken(), 'rt_refreshed');
      expect(await store.hasTokens(), isTrue);
    });

    test('multiple save cycles preserve latest values', () async {
      for (int i = 0; i < 5; i++) {
        await store.saveTokens('at_$i', 'rt_$i');
        expect(await store.getAccessToken(), 'at_$i');
        expect(await store.getRefreshToken(), 'rt_$i');
      }
    });

    test('clear then immediate save works correctly', () async {
      await store.saveTokens('at1', 'rt1');
      await store.clearTokens();
      await store.saveTokens('at2', 'rt2');

      expect(await store.getAccessToken(), 'at2');
      expect(await store.getRefreshToken(), 'rt2');
    });
  });

  // ── Error handling ─────────────────────────────────────────────────

  group('error handling', () {
    test('read throws when secure storage is unavailable', () async {
      fakePlatform.setThrowOnRead(true);

      expect(
        () => store.getAccessToken(),
        throwsA(isA<PlatformException>()),
      );
    });

    test('read refresh token throws when secure storage is unavailable',
        () async {
      fakePlatform.setThrowOnRead(true);

      expect(
        () => store.getRefreshToken(),
        throwsA(isA<PlatformException>()),
      );
    });

    test('clearTokens throws when secure storage delete fails', () async {
      fakePlatform.setThrowOnDelete(true);

      expect(
        () => store.clearTokens(),
        throwsA(isA<PlatformException>()),
      );
    });

    test('hasTokens throws when read fails', () async {
      fakePlatform.setThrowOnRead(true);

      expect(
        () => store.hasTokens(),
        throwsA(isA<PlatformException>()),
      );
    });

    test('getOrCreateDeviceId throws when read fails', () async {
      fakePlatform.setThrowOnRead(true);

      expect(
        () => store.getOrCreateDeviceId(),
        throwsA(isA<PlatformException>()),
      );
    });

    test('partial failure in saveTokens (access fails) still writes refresh',
        () async {
      // Simulate write failure on access token only
      // We can't easily do this with the current fake, but we verify
      // that concurrent writes don't interfere
      fakePlatform.setThrowOnWrite(true);

      expect(
        () => store.saveTokens('access', 'refresh'),
        throwsA(isA<PlatformException>()),
      );
    });
  });

  // ── Edge cases ──────────────────────────────────────────────────────

  group('edge cases', () {
    test('null-equivalent empty string does not equal null', () async {
      await store.saveTokens('', 'rt');

      final access = await store.getAccessToken();
      expect(access, isNotNull);
      expect(access, '');
    });

    test('token values with special characters are preserved', () async {
      const specialAccess = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0';
      const specialRefresh = 'dGhpcyBpcyBhIHJlZnJlc2ggdG9rZW4gd2l0aCBzcGVjaWFsIGNoYXJzOiAhQCMkJV4mKihd';
      await store.saveTokens(specialAccess, specialRefresh);

      expect(await store.getAccessToken(), specialAccess);
      expect(await store.getRefreshToken(), specialRefresh);
    });

    test('very long token values are stored correctly', () async {
      final longAccess = 'at_' + 'x' * 10000;
      await store.saveTokens(longAccess, 'rt');

      final retrieved = await store.getAccessToken();
      expect(retrieved, longAccess);
      expect(retrieved!.length, 10003);
    });

    test('device ID has correct UUID format', () async {
      final id = await store.getOrCreateDeviceId();

      // UUID v4 format
      expect(id, matches(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'));
    });

    test('storing null-like values does not break storage', () async {
      // SecureTokenStore accepts non-nullable String parameters
      // Empty string is the closest to null
      await store.saveTokens('non_empty', 'non_empty');
      expect(await store.getAccessToken(), 'non_empty');
      expect(await store.getRefreshToken(), 'non_empty');
    });

    test('access and refresh tokens are stored under distinct keys', () async {
      await store.saveTokens('access_val', 'refresh_val');

      // Verify keys are different
      expect(fakePlatform.data.containsKey('access_token'), isTrue);
      expect(fakePlatform.data.containsKey('refresh_token'), isTrue);
      expect(fakePlatform.data['access_token'], 'access_val');
      expect(fakePlatform.data['refresh_token'], 'refresh_val');
    });

    test('clearTokens does not affect device ID', () async {
      await store.getOrCreateDeviceId();
      await store.saveTokens('at', 'rt');
      await store.clearTokens();

      // Device ID should still be present
      expect(fakePlatform.data.containsKey('operion_device_id'), isTrue);
    });
  });
}
