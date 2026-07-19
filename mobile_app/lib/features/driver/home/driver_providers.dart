import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/endpoints/driver_endpoints.dart';
import '../../../shared/models/transport.dart';

/// Provides a singleton [DriverEndpoints] wired to the shared [ApiClient]
/// from the auth layer.
final driverEndpointsProvider = Provider<DriverEndpoints>((ref) {
  return DriverEndpoints(ref.read(apiClientProvider));
});

/// Fetches the driver's "My Day" aggregate data from the API.
///
/// The returned map is expected to contain keys such as:
/// - `activeTransports` (int) — number of currently active transports
/// - `nextStop` (Map) — `{ "destination": String, "time": String }`
/// - `transports` (List) — list of transport JSON objects
/// - `messages` (List) — list of message JSON objects
/// - `lastUpdated` (String) — ISO-8601 timestamp
///
/// Throws on network or server errors; the calling widget should handle
/// loading / error states.
final myDayProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final endpoints = ref.watch(driverEndpointsProvider);
  final response = await endpoints.getMyDay();
  return response.data as Map<String, dynamic>;
});

/// Fetches all transports assigned to the current driver.
///
/// Returns an empty list when no transports are assigned.
final transportsProvider = FutureProvider<List<Transport>>((ref) async {
  final endpoints = ref.watch(driverEndpointsProvider);
  final response = await endpoints.getTransports();
  final list = response.data as List;
  return list
      .map((json) => Transport.fromJson(json as Map<String, dynamic>))
      .toList();
});

/// Fetches a single transport by [id].
///
/// Used by [TransportDetailScreen] to display full transport information.
final transportDetailProvider =
    FutureProvider.family<Transport, String>((ref, id) async {
  final endpoints = ref.watch(driverEndpointsProvider);
  final response = await endpoints.getTransport(id);
  return Transport.fromJson(response.data as Map<String, dynamic>);
});

/// Tracks a pending status update request.
///
/// Set to a record of `transportId` and `newStatus` while an update is in
/// progress, and reset to `null` on completion (success or failure).
///
/// Widgets can watch this provider to show a loading indicator on the
/// relevant status button.
final statusUpdateProvider =
    StateProvider<({String transportId, String newStatus})?>((ref) => null);

/// Selected tab index for the driver bottom navigation shell.
///
/// 0 = Home (My Day), 1 = Transports, 2 = Messages, 3 = Profile.
final driverTabProvider = StateProvider<int>((ref) => 0);
