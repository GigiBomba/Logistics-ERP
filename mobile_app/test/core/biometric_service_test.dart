import 'package:flutter_test/flutter_test.dart';
import 'package:local_auth/local_auth.dart' show LocalAuthentication, AuthenticationOptions, BiometricType;
import 'package:local_auth_platform_interface/local_auth_platform_interface.dart'
    show AuthMessages;

import 'package:operion_mobile/core/auth/biometric_service.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Fake LocalAuthentication
// ─────────────────────────────────────────────────────────────────────────────

class _FakeLocalAuthentication implements LocalAuthentication {
  bool _canCheckBiometrics;
  bool _deviceSupported;
  List<BiometricType> _availableBiometrics;
  bool _authenticateResult;
  bool _shouldThrowOnAuthenticate;

  _FakeLocalAuthentication({
    bool canCheckBiometrics = false,
    bool deviceSupported = false,
    List<BiometricType> availableBiometrics = const [],
    bool authenticateResult = true,
    bool shouldThrowOnAuthenticate = false,
  })  : _canCheckBiometrics = canCheckBiometrics,
        _deviceSupported = deviceSupported,
        _availableBiometrics = availableBiometrics,
        _authenticateResult = authenticateResult,
        _shouldThrowOnAuthenticate = shouldThrowOnAuthenticate;

  @override
  Future<bool> get canCheckBiometrics async => _canCheckBiometrics;

  @override
  Future<bool> isDeviceSupported() async => _deviceSupported;

  @override
  Future<List<BiometricType>> getAvailableBiometrics() async =>
      _availableBiometrics;

  @override
  Future<bool> authenticate({
    required String localizedReason,
    Iterable<AuthMessages> authMessages = const [],
    AuthenticationOptions options = const AuthenticationOptions(),
  }) async {
    if (_shouldThrowOnAuthenticate) {
      throw Exception('Auth error');
    }
    return _authenticateResult;
  }

  @override
  Future<bool> stopAuthentication() async => true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  group('BiometricService', () {
    // ── isAvailable() ───────────────────────────────────────────────────

    test('isAvailable with canCheckBiometrics=true, deviceSupported=true → true',
        () async {
      final fakeAuth = _FakeLocalAuthentication(
        canCheckBiometrics: true,
        deviceSupported: true,
      );
      final service = BiometricService(auth: fakeAuth);

      final result = await service.isAvailable();

      expect(result, isTrue);
    });

    test('isAvailable with canCheckBiometrics=false, deviceSupported=true → true',
        () async {
      final fakeAuth = _FakeLocalAuthentication(
        canCheckBiometrics: false,
        deviceSupported: true,
      );
      final service = BiometricService(auth: fakeAuth);

      final result = await service.isAvailable();

      expect(result, isTrue);
    });

    test('isAvailable with canCheckBiometrics=true, deviceSupported=false → true',
        () async {
      final fakeAuth = _FakeLocalAuthentication(
        canCheckBiometrics: true,
        deviceSupported: false,
      );
      final service = BiometricService(auth: fakeAuth);

      final result = await service.isAvailable();

      expect(result, isTrue);
    });

    test('isAvailable with canCheckBiometrics=false, deviceSupported=false → false',
        () async {
      final fakeAuth = _FakeLocalAuthentication(
        canCheckBiometrics: false,
        deviceSupported: false,
      );
      final service = BiometricService(auth: fakeAuth);

      final result = await service.isAvailable();

      expect(result, isFalse);
    });

    test('isAvailable returns false when canCheckBiometrics throws', () async {
      final throwingAuth = _ThrowingLocalAuthentication(
        throwOnCanCheck: true,
      );
      final service = BiometricService(auth: throwingAuth);

      final result = await service.isAvailable();

      expect(result, isFalse);
    });

    test('isAvailable returns false when isDeviceSupported throws', () async {
      final throwingAuth = _ThrowingLocalAuthentication(
        throwOnDeviceSupported: true,
      );
      final service = BiometricService(auth: throwingAuth);

      final result = await service.isAvailable();

      expect(result, isFalse);
    });

    // ── getAvailableTypes() ─────────────────────────────────────────────

    test('getAvailableTypes returns list of biometric types', () async {
      final fakeAuth = _FakeLocalAuthentication(
        availableBiometrics: [
          BiometricType.fingerprint,
          BiometricType.face,
        ],
      );
      final service = BiometricService(auth: fakeAuth);

      final types = await service.getAvailableTypes();

      expect(types, hasLength(2));
      expect(types, contains(BiometricType.fingerprint));
      expect(types, contains(BiometricType.face));
    });

    test('getAvailableTypes returns empty list when none available', () async {
      final fakeAuth = _FakeLocalAuthentication(
        availableBiometrics: [],
      );
      final service = BiometricService(auth: fakeAuth);

      final types = await service.getAvailableTypes();

      expect(types, isEmpty);
    });

    test('getAvailableTypes returns empty list on exception', () async {
      final throwingAuth = _ThrowingLocalAuthentication(
        throwOnGetBiometrics: true,
      );
      final service = BiometricService(auth: throwingAuth);

      final types = await service.getAvailableTypes();

      expect(types, isEmpty);
    });

    // ── authenticate() ──────────────────────────────────────────────────

    test('authenticate returns true when user authenticates successfully',
        () async {
      final fakeAuth = _FakeLocalAuthentication(authenticateResult: true);
      final service = BiometricService(auth: fakeAuth);

      final result = await service.authenticate(reason: 'Log in');

      expect(result, isTrue);
    });

    test('authenticate returns false when user cancels', () async {
      final fakeAuth = _FakeLocalAuthentication(authenticateResult: false);
      final service = BiometricService(auth: fakeAuth);

      final result = await service.authenticate(reason: 'Log in');

      expect(result, isFalse);
    });

    test('authenticate returns false on exception', () async {
      final fakeAuth = _FakeLocalAuthentication(
        shouldThrowOnAuthenticate: true,
      );
      final service = BiometricService(auth: fakeAuth);

      final result = await service.authenticate(reason: 'Log in');

      expect(result, isFalse);
    });

    test('authenticate passes the localized reason to the platform', () async {
      String? capturedReason;
      final capturingAuth = _CapturingLocalAuthentication();
      capturingAuth.onAuthenticate = (String reason, AuthenticationOptions opts) {
        capturedReason = reason;
        return true;
      };
      final service = BiometricService(auth: capturingAuth);

      await service.authenticate(reason: 'Authenticate to unlock');

      expect(capturedReason, 'Authenticate to unlock');
    });

    test('authenticate uses biometricOnly and stickyAuth options', () async {
      AuthenticationOptions? capturedOptions;
      final capturingAuth = _CapturingLocalAuthentication();
      capturingAuth.onAuthenticate = (reason, options) {
        capturedOptions = options;
        return true;
      };
      final service = BiometricService(auth: capturingAuth);

      await service.authenticate(reason: 'Test');

      expect(capturedOptions, isNotNull);
      expect(capturedOptions!.biometricOnly, isTrue);
      expect(capturedOptions!.stickyAuth, isTrue);
    });

    // ── Constructor ─────────────────────────────────────────────────────

    test('constructor creates default LocalAuthentication when no auth provided',
        () {
      // Should not throw
      expect(() => BiometricService(), returnsNormally);
    });
  });
}

// ── Additional fake implementations ──────────────────────────────────────────

class _ThrowingLocalAuthentication implements LocalAuthentication {
  final bool throwOnCanCheck;
  final bool throwOnDeviceSupported;
  final bool throwOnGetBiometrics;

  _ThrowingLocalAuthentication({
    this.throwOnCanCheck = false,
    this.throwOnDeviceSupported = false,
    this.throwOnGetBiometrics = false,
  });

  @override
  Future<bool> get canCheckBiometrics async {
    if (throwOnCanCheck) throw Exception('canCheckBiometrics failed');
    return false;
  }

  @override
  Future<bool> isDeviceSupported() async {
    if (throwOnDeviceSupported) throw Exception('isDeviceSupported failed');
    return false;
  }

  @override
  Future<List<BiometricType>> getAvailableBiometrics() async {
    if (throwOnGetBiometrics) throw Exception('getAvailableBiometrics failed');
    return [];
  }

  @override
  Future<bool> authenticate({
    required String localizedReason,
    Iterable<AuthMessages> authMessages = const [],
    AuthenticationOptions options = const AuthenticationOptions(),
  }) async {
    return true;
  }

  @override
  Future<bool> stopAuthentication() async => true;
}

class _CapturingLocalAuthentication implements LocalAuthentication {
  bool Function(String reason, AuthenticationOptions options)? onAuthenticate;

  @override
  Future<bool> get canCheckBiometrics async => true;

  @override
  Future<bool> isDeviceSupported() async => true;

  @override
  Future<List<BiometricType>> getAvailableBiometrics() async =>
      [BiometricType.fingerprint];

  @override
  Future<bool> authenticate({
    required String localizedReason,
    Iterable<AuthMessages> authMessages = const [],
    AuthenticationOptions options = const AuthenticationOptions(),
  }) async {
    return onAuthenticate?.call(localizedReason, options) ?? true;
  }

  @override
  Future<bool> stopAuthentication() async => true;
}
