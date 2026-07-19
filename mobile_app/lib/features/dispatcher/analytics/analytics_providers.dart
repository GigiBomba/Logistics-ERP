import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_providers.dart';

/// Period filter for analytics data.
enum AnalyticsPeriod { thisMonth, lastMonth }

// ---------------------------------------------------------------------------
// Individual analytics data providers
// ---------------------------------------------------------------------------

/// Fetches the analytics overview from `/api/v1/mobile/analytics/overview`.
///
/// Expected response keys:
/// - `totalRevenue` (num)
/// - `totalCosts` (num)
/// - `profit` (num)
/// - `period` (String)
final analyticsOverviewProvider =
    FutureProvider.family<Map<String, dynamic>, AnalyticsPeriod>(
        (ref, period) async {
  final apiClient = ref.read(apiClientProvider);
  final response = await apiClient.get(
    '/api/v1/mobile/analytics/overview',
    queryParameters: {'period': _periodParam(period)},
  );
  final data = response.data;
  if (data is Map<String, dynamic>) return data;
  throw StateError('Unexpected response type: ${data.runtimeType}');
});

/// Fetches financial summary from `/api/v1/mobile/analytics/financial`.
///
/// Expected response keys per period:
/// - `revenue` (num), `costs` (num), `profit` (num)
/// - `revenueTrend` (num), `costsTrend` (num), `profitTrend` (num)
final analyticsFinancialProvider =
    FutureProvider.family<Map<String, dynamic>, AnalyticsPeriod>(
        (ref, period) async {
  final apiClient = ref.read(apiClientProvider);
  final response = await apiClient.get(
    '/api/v1/mobile/analytics/financial',
    queryParameters: {'period': _periodParam(period)},
  );
  final data = response.data;
  if (data is Map<String, dynamic>) return data;
  throw StateError('Unexpected response type: ${data.runtimeType}');
});

/// Fetches fleet utilization from `/api/v1/mobile/analytics/fleet/utilization`.
///
/// Expected response keys:
/// - `activeTrucks` (int)
/// - `totalTrucks` (int)
/// - `utilizationPercent` (double, 0–100)
final analyticsFleetUtilizationProvider =
    FutureProvider.family<Map<String, dynamic>, AnalyticsPeriod>(
        (ref, period) async {
  final apiClient = ref.read(apiClientProvider);
  final response = await apiClient.get(
    '/api/v1/mobile/analytics/fleet/utilization',
    queryParameters: {'period': _periodParam(period)},
  );
  final data = response.data;
  if (data is Map<String, dynamic>) return data;
  throw StateError('Unexpected response type: ${data.runtimeType}');
});

/// Fetches top clients revenue from `/api/v1/mobile/analytics/revenue-by-client`.
///
/// Expected response: a list of objects with keys:
/// - `clientName` (String)
/// - `revenue` (num)
final analyticsTopClientsProvider =
    FutureProvider.family<List<Map<String, dynamic>>, AnalyticsPeriod>(
        (ref, period) async {
  final apiClient = ref.read(apiClientProvider);
  final response = await apiClient.get(
    '/api/v1/mobile/analytics/revenue-by-client',
    queryParameters: {'period': _periodParam(period), 'limit': 3},
  );
  final data = response.data;
  if (data is List) {
    return data.cast<Map<String, dynamic>>();
  }
  return [];
});

/// Fetches top driver performance from `/api/v1/mobile/analytics/driver`.
///
/// Expected response: a list of objects with keys:
/// - `driverName` (String)
/// - `trips` (int)
/// - `profit` (num)
final analyticsDriverPerformanceProvider =
    FutureProvider.family<List<Map<String, dynamic>>, AnalyticsPeriod>(
        (ref, period) async {
  final apiClient = ref.read(apiClientProvider);
  final response = await apiClient.get(
    '/api/v1/mobile/analytics/driver',
    queryParameters: {'period': _periodParam(period), 'limit': 3},
  );
  final data = response.data;
  if (data is List) {
    return data.cast<Map<String, dynamic>>();
  }
  return [];
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Converts [AnalyticsPeriod] to an API query parameter value.
String _periodParam(AnalyticsPeriod period) {
  return switch (period) {
    AnalyticsPeriod.thisMonth => 'this_month',
    AnalyticsPeriod.lastMonth => 'last_month',
  };
}
