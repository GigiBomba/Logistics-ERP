import 'package:dio/dio.dart';

import '../api_client.dart';

/// Endpoint methods for delta-synchronisation with the server.
class SyncEndpoints {
  final ApiClient client;

  SyncEndpoints(this.client);

  /// Fetch delta changes for a specific [entityType] since [cursor].
  Future<Response> syncEntity(String entityType, {String? cursor}) {
    final params = <String, dynamic>{'entity': entityType};
    if (cursor != null) params['since'] = cursor;
    return client.get('/api/v1/mobile/sync', queryParameters: params);
  }

  /// Full (non-delta) sync for a specific [entityType].
  Future<Response> syncEntityFull(String entityType) =>
      client.get('/api/v1/mobile/sync', queryParameters: {'entity': entityType, 'full': 'true'});
}
