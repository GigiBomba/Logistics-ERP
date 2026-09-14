import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/network/endpoints/freight_exchange_endpoints.dart';
import '../models/freight_load.dart';

// ── Foundation providers ─────────────────────────────────────────────────

final freightExchangeEndpointsProvider = Provider<FreightExchangeEndpoints>(
  (ref) {
    final apiClient = ref.watch(apiClientProvider);
    return FreightExchangeEndpoints(apiClient);
  },
);

// ── State providers ──────────────────────────────────────────────────────

/// Possible states of the Freight Exchange screen.
sealed class FreightExchangeState {
  const FreightExchangeState();
}

class FreightExchangeInitial extends FreightExchangeState {
  const FreightExchangeInitial();
}

class FreightExchangeLoading extends FreightExchangeState {
  const FreightExchangeLoading();
}

class FreightExchangeData extends FreightExchangeState {
  final List<FreightLoad> loads;
  final String? origin;
  final String? destination;
  final String? date;
  final String? cargoType;

  const FreightExchangeData({
    required this.loads,
    this.origin,
    this.destination,
    this.date,
    this.cargoType,
  });

  FreightExchangeData copyWith({
    List<FreightLoad>? loads,
    String? origin,
    String? destination,
    String? date,
    String? cargoType,
  }) {
    return FreightExchangeData(
      loads: loads ?? this.loads,
      origin: origin ?? this.origin,
      destination: destination ?? this.destination,
      date: date ?? this.date,
      cargoType: cargoType ?? this.cargoType,
    );
  }
}

class FreightExchangeError extends FreightExchangeState {
  final String messageKey;
  const FreightExchangeError({required this.messageKey});
}

/// Manages the freight-exchange list lifecycle.
class FreightExchangeNotifier extends StateNotifier<FreightExchangeState> {
  final FreightExchangeEndpoints _endpoints;

  FreightExchangeNotifier(this._endpoints)
      : super(const FreightExchangeInitial());

  /// Fetch loads with optional filters.
  Future<void> loadLoads({
    String? origin,
    String? destination,
    String? date,
    String? cargoType,
  }) async {
    state = const FreightExchangeLoading();
    try {
      final loads = await _endpoints.listLoads(
        origin: origin,
        destination: destination,
        date: date,
        cargoType: cargoType,
      );
      state = FreightExchangeData(
        loads: loads,
        origin: origin,
        destination: destination,
        date: date,
        cargoType: cargoType,
      );
    } catch (e) {
      state = const FreightExchangeError(messageKey: 'freightExchange_error');
    }
  }

  /// Refresh the current query.
  Future<void> refresh({
    String? origin,
    String? destination,
    String? date,
    String? cargoType,
  }) async {
    return loadLoads(
      origin: origin,
      destination: destination,
      date: date,
      cargoType: cargoType,
    );
  }

  /// Import a load as a new trip.
  Future<void> importLoad(FreightLoad load) async {
    final current = state;
    if (current is! FreightExchangeData) return;
    try {
      await _endpoints.importLoad(
        providerId: load.providerId,
        loadId: load.providerLoadId,
      );
    } catch (e) {
      state = const FreightExchangeError(messageKey: 'freightExchange_error');
    }
  }

  /// Evaluate a single load.
  Future<Map<String, dynamic>?> evaluateLoad(FreightLoad load) async {
    final current = state;
    if (current is! FreightExchangeData) return null;
    try {
      return await _endpoints.evaluateLoad(
        providerId: load.providerId,
        loadId: load.providerLoadId,
      );
    } catch (e) {
      state = const FreightExchangeError(messageKey: 'freightExchange_error');
      return null;
    }
  }
}

final freightExchangeStateProvider =
    StateNotifierProvider<FreightExchangeNotifier, FreightExchangeState>(
  (ref) {
    final endpoints = ref.watch(freightExchangeEndpointsProvider);
    return FreightExchangeNotifier(endpoints);
  },
);
