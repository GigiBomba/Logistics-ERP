import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/models/vehicle.dart';
import '../home/driver_providers.dart';

/// Provider for the driver's currently assigned vehicle.
///
/// Returns `null` gracefully when no vehicle is assigned (not treated as an
/// error). Throws on actual network/server failures so the calling widget can
/// show an error/retry state.
final vehicleProvider = FutureProvider<Vehicle?>((ref) async {
  final endpoints = ref.read(driverEndpointsProvider);
  final response = await endpoints.getVehicle();
  if (response.statusCode == 404) return null;
  final data = response.data;
  if (data is Map<String, dynamic>) return Vehicle.fromJson(data);
  return null;
});
