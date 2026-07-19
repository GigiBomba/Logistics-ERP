import 'package:dio/dio.dart';

import '../api_client.dart';

/// Endpoint methods for push-notification device registration.
class DeviceEndpoints {
  final ApiClient client;

  DeviceEndpoints(this.client);

  /// Register this device for push notifications.
  ///
  /// [token] is the FCM registration token.
  /// [platform] should be `"ios"` or `"android"`.
  Future<Response> registerDevice(
    String token,
    String platform, {
    String? deviceId,
    String? deviceName,
  }) =>
      client.post('/api/v1/mobile/devices/register', data: {
        'token': token,
        'platform': platform,
        if (deviceId != null) 'device_id': deviceId,
        if (deviceName != null) 'device_name': deviceName,
      });

  /// Unregister this device from push notifications.
  Future<Response> unregisterDevice() =>
      client.delete('/api/v1/mobile/devices/register');
}
