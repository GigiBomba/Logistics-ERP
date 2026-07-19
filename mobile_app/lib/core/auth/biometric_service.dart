import 'package:local_auth/local_auth.dart';

/// Wraps the [LocalAuthentication] plugin with convenience methods for
/// checking availability and performing biometric authentication.
///
/// Usage:
/// ```dart
/// final bio = BiometricService();
/// if (await bio.isAvailable()) {
///   final ok = await bio.authenticate(reason: 'Log in');
/// }
/// ```
class BiometricService {
  final LocalAuthentication _auth;

  BiometricService({LocalAuthentication? auth})
      : _auth = auth ?? LocalAuthentication();

  /// Returns `true` if the device supports biometric authentication (face,
  /// fingerprint, or iris) and the user has enrolled at least one biometric.
  Future<bool> isAvailable() async {
    try {
      final canCheck = await _auth.canCheckBiometrics;
      final deviceSupported = await _auth.isDeviceSupported();
      return canCheck || deviceSupported;
    } catch (_) {
      return false;
    }
  }

  /// Returns the list of biometric types the device can recognise
  /// (e.g. [BiometricType.fingerprint], [BiometricType.face]).
  Future<List<BiometricType>> getAvailableTypes() async {
    try {
      return await _auth.getAvailableBiometrics();
    } catch (_) {
      return [];
    }
  }

  /// Prompts the user to authenticate using biometrics.
  ///
  /// [reason] is the localized message shown in the system dialog (e.g.
  /// "Authenticate to unlock Operion").
  ///
  /// Returns `true` when the user successfully authenticates, `false` when
  /// the user cancels, the device has no enrolled biometrics, or biometrics
  /// are unavailable.
  Future<bool> authenticate({required String reason}) async {
    try {
      return await _auth.authenticate(
        localizedReason: reason,
        options: const AuthenticationOptions(
          stickyAuth: true,
          biometricOnly: true,
        ),
      );
    } on Exception catch (_) {
      // Return false for any auth-related failure (cancellation,
      // unavailable, not enrolled, lockout, etc.) so callers don't
      // have to catch platform-specific exceptions.
      return false;
    }
  }
}
