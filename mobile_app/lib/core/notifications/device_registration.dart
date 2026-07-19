import 'dart:developer' as developer;
import 'dart:io' show Platform;

import '../network/endpoints/device_endpoints.dart';
import 'push_service.dart';

/// Handles registering and unregistering the device's FCM push token with
/// the Operion backend.
class DeviceRegistration {
  final DeviceEndpoints _endpoints;
  final PushService _pushService;

  DeviceRegistration(this._endpoints, this._pushService);

  /// Returns the platform identifier used in the registration payload.
  ///
  /// Returns `'ios'` on iOS, `'android'` on Android, and `'unknown'` for
  /// any other platform (web, desktop).
  String get _platform {
    try {
      if (Platform.isIOS) return 'ios';
      if (Platform.isAndroid) return 'android';
    } catch (_) {
      // Platform may throw on web – fall through.
    }
    return 'unknown';
  }

  /// Registers the current device token with the backend.
  ///
  /// Sends a POST request containing the FCM token and platform identifier.
  /// If the token cannot be obtained, registration is skipped with a log
  /// warning.
  Future<void> register() async {
    final token = _pushService.token ?? await _pushService.getToken();

    if (token == null || token.isEmpty) {
      developer.log(
        'DeviceRegistration: no token available – skipping registration',
        name: 'DeviceRegistration',
      );
      return;
    }

    try {
      await _endpoints.registerDevice(token, _platform);
      developer.log(
        'DeviceRegistration: registered token (${token.substring(0, 8)}…)',
        name: 'DeviceRegistration',
      );
    } catch (e) {
      developer.log(
        'DeviceRegistration: registration failed → $e',
        name: 'DeviceRegistration',
      );
      // Registration failures are non-critical; the token will be refreshed
      // and re-registered on next app launch.
    }
  }

  /// Unregisters the current device token from the backend.
  ///
  /// Should be called on logout so the user stops receiving push
  /// notifications on this device.
  Future<void> unregister() async {
    final token = _pushService.token;
    if (token == null) {
      developer.log(
        'DeviceRegistration: no token to unregister',
        name: 'DeviceRegistration',
      );
      return;
    }

    try {
      await _endpoints.unregisterDevice();
      developer.log(
        'DeviceRegistration: unregistered token (${token.substring(0, 8)}…)',
        name: 'DeviceRegistration',
      );
    } catch (e) {
      developer.log(
        'DeviceRegistration: unregistration failed → $e',
        name: 'DeviceRegistration',
      );
    }
  }
}
