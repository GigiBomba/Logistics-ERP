import 'package:dio/dio.dart';

import '../api_client.dart';

/// Endpoint methods for dispatcher-related API calls.
class DispatcherEndpoints {
  final ApiClient client;

  DispatcherEndpoints(this.client);

  /// Fetch the dispatcher overview dashboard data.
  Future<Response> getOverview() => client.get('/api/v1/mobile/dispatcher/overview');

  /// Fetch the live fleet positions.
  Future<Response> getFleet() => client.get('/api/v1/mobile/dispatcher/fleet');

  /// Fetch all active jobs.
  Future<Response> getJobs() => client.get('/api/v1/mobile/dispatcher/jobs');

  /// Fetch all drivers.
  Future<Response> getDrivers() => client.get('/api/v1/mobile/dispatcher/drivers');

  /// Fetch all alerts.
  Future<Response> getAlerts() => client.get('/api/v1/mobile/dispatcher/alerts');

  /// Approve an action identified by [id].
  Future<Response> approveAction(String id) =>
      client.post('/api/v1/mobile/dispatcher/approvals/$id/approve');

  /// Reject an action identified by [id] with an optional [reason].
  Future<Response> rejectAction(String id, {String? reason}) =>
      client.post('/api/v1/mobile/dispatcher/approvals/$id/reject',
          data: {'reason': reason});

  /// Reassign [transportId] to a different driver identified by [driverId].
  Future<Response> reassignTransport(String transportId, String driverId) =>
      client.post('/api/v1/mobile/dispatcher/jobs/$transportId/reassign',
          data: {'driver_id': driverId});
}
