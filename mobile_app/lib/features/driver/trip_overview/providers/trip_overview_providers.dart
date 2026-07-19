import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/providers/driver_providers.dart';
import '../../models/driver_trip_overview.dart';

final tripOverviewProvider =
    FutureProvider<DriverTripOverview>((ref) async {
  final endpoints = ref.watch(driverEndpointsProvider);
  final response = await endpoints.getTripOverview();
  final data = response.data;
  if (data is Map<String, dynamic>) {
    return DriverTripOverview.fromJson(data);
  }
  throw StateError('Unexpected response type: ${data.runtimeType}');
});
