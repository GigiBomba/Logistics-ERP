import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/auth/auth_providers.dart';
import '../../../../core/providers/driver_providers.dart';
import '../../models/route_share_geometry.dart';

/// Fetches route share geometry from the backend.
///
/// Calls GET /api/v1/mobile/driver/transports/{transport_id}/route-share.
/// The transport_id is resolved server-side from the JWT for the driver's
/// own assigned transport.
final routeShareGeometryProvider =
    FutureProvider<RouteShareGeometry>((ref) async {
  final endpoints = ref.watch(driverEndpointsProvider);
  final user = ref.watch(currentUserProvider);
  if (user == null) throw StateError('User not authenticated');

  final response = await endpoints.getRouteShare();
  final data = response.data;
  if (data is Map<String, dynamic>) {
    return RouteShareGeometry.fromJson(data);
  }
  throw StateError('Unexpected response type: ${data.runtimeType}');
});
