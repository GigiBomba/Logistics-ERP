import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../auth/auth_providers.dart';
import '../network/endpoints/driver_endpoints.dart';

/// Shared [DriverEndpoints] wired to the global [ApiClient].
/// Defined once, imported by any feature that needs driver API access.
final driverEndpointsProvider = Provider<DriverEndpoints>((ref) {
  return DriverEndpoints(ref.read(apiClientProvider));
});
