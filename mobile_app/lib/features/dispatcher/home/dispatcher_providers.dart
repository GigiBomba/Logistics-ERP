import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/network/endpoints/dispatcher_endpoints.dart';
import '../../../shared/models/fleet_position.dart';

/// Provides a singleton [DispatcherEndpoints] wired to the shared [ApiClient]
/// from the auth layer.
final dispatcherEndpointsProvider = Provider<DispatcherEndpoints>((ref) {
  return DispatcherEndpoints(ref.read(apiClientProvider));
});

/// Fetches the dispatcher overview aggregate data from the API.
///
/// The returned map is expected to contain keys such as:
/// - `activeJobs` (int) — number of currently active jobs
/// - `activeDrivers` (int) — number of currently active drivers
/// - `openAlerts` (int) — number of open / unacknowledged alerts
/// - `vehiclesOnRoad` (int) — number of vehicles currently in transit
/// - `lastUpdated` (String) — ISO-8601 timestamp of the last refresh
///
/// Throws on network or server errors; the calling widget should handle
/// loading / error states.
final dispatcherOverviewProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final endpoints = ref.watch(dispatcherEndpointsProvider);
  final response = await endpoints.getOverview();
  final data = response.data;
  if (data is Map<String, dynamic>) return data;
  throw StateError('Unexpected response type: ${data.runtimeType}');
});

/// Fetches live fleet positions.
///
/// Each item is expected to contain keys such as:
/// - `vehicle_id` (String)
/// - `plate` (String)
/// - `driver_name` (String)
/// - `lat` / `lng` (double)
/// - `status` (String)
/// - `last_update` (String — ISO-8601)
final fleetPositionsProvider = FutureProvider<List<FleetPosition>>((ref) async {
  final endpoints = ref.watch(dispatcherEndpointsProvider);
  final response = await endpoints.getFleet();
  final data = response.data;
  if (data is List) {
    return data
        .map((e) => FleetPosition.fromJson(e as Map<String, dynamic>))
        .toList();
  }
  return [];
});

/// Fetches all active jobs / transport orders.
final dispatcherJobsProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final endpoints = ref.watch(dispatcherEndpointsProvider);
  final response = await endpoints.getJobs();
  final data = response.data;
  if (data is! List) return [];
  return data.cast<Map<String, dynamic>>();
});

/// Fetches all drivers.
final dispatcherDriversProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final endpoints = ref.watch(dispatcherEndpointsProvider);
  final response = await endpoints.getDrivers();
  final data = response.data;
  if (data is! List) return [];
  return data.cast<Map<String, dynamic>>();
});

/// Fetches all alerts / notifications.
final dispatcherAlertsProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final endpoints = ref.watch(dispatcherEndpointsProvider);
  final response = await endpoints.getAlerts();
  final data = response.data;
  if (data is! List) return [];
  return data.cast<Map<String, dynamic>>();
});

/// Provides a single alert by its [alertId] from the cached alerts list.
///
/// Returns `null` while loading or when the alert is not found.
final dispatcherAlertDetailProvider =
    FutureProvider.family<Map<String, dynamic>?, int>((ref, alertId) async {
  final alerts = await ref.watch(dispatcherAlertsProvider.future);
  return alerts.cast<Map<String, dynamic>?>().firstWhere(
        (alert) {
          final id = alert!['id'];
          if (id is int) return id == alertId;
          if (id is String) return int.tryParse(id) == alertId;
          return false;
        },
        orElse: () => null,
      );
});

/// Selected tab index for the dispatcher bottom navigation shell.
///
/// 0 = Overview, 1 = Fleet Tracker, 2 = AI Copilot, 3 = More.
final dispatcherTabProvider = StateProvider<int>((ref) => 0);
