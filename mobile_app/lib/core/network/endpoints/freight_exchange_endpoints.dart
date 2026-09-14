import 'package:dio/dio.dart';

import '../api_client.dart';
import '../../../features/freight_exchange/models/freight_load.dart';

/// Endpoints for the Freight Exchange API.
///
/// All endpoints sit under /api/v1/freight/* and require JWT auth.
class FreightExchangeEndpoints {
  final ApiClient _client;

  FreightExchangeEndpoints(this._client);

  /// List freight loads across connected providers.
  Future<List<FreightLoad>> listLoads({
    String? origin,
    String? destination,
    String? date,
    String? cargoType,
    int limit = 50,
    CancelToken? cancelToken,
  }) async {
    final response = await _client.dio.get(
      '/api/v1/freight/loads',
      queryParameters: {
        if (origin != null && origin.isNotEmpty) 'origin': origin,
        if (destination != null && destination.isNotEmpty)
          'destination': destination,
        if (date != null && date.isNotEmpty) 'date': date,
        if (cargoType != null && cargoType.isNotEmpty) 'cargo_type': cargoType,
        'limit': limit,
      },
      cancelToken: cancelToken,
    );
    final data = response.data as List<dynamic>;
    return data
        .map((e) => FreightLoad.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Import a freight exchange load as an Operion trip.
  Future<Map<String, dynamic>> importLoad({
    required String providerId,
    required String loadId,
    CancelToken? cancelToken,
  }) async {
    final response = await _client.dio.post(
      '/api/v1/freight/loads/$providerId/$loadId/import',
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  /// Evaluate a load's profitability and risk.
  Future<Map<String, dynamic>> evaluateLoad({
    required String providerId,
    required String loadId,
    CancelToken? cancelToken,
  }) async {
    final response = await _client.dio.get(
      '/api/v1/freight/loads/$providerId/$loadId/evaluate',
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  /// Find the best trucks for a given load.
  Future<Map<String, dynamic>> matchLoad({
    required String providerId,
    required String loadId,
    int topN = 5,
    CancelToken? cancelToken,
  }) async {
    final response = await _client.get(
      '/api/v1/freight/loads/$providerId/$loadId/match',
      queryParameters: {'top_n': topN},
    );
    return response.data as Map<String, dynamic>;
  }

  /// List all connected providers with status and capabilities.
  Future<List<Map<String, dynamic>>> listProviders({
    CancelToken? cancelToken,
  }) async {
    final response = await _client.get('/api/v1/freight/providers');
    final data = response.data as Map<String, dynamic>;
    final providers = data['providers'] as List<dynamic>? ?? [];
    return providers.cast<Map<String, dynamic>>();
  }
}
