import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/freight_exchange_endpoints.dart';
import 'package:operion_mobile/features/freight_exchange/models/freight_load.dart';
import 'package:operion_mobile/features/freight_exchange/providers/freight_exchange_providers.dart';

// ── Fake endpoints for notifier tests ─────────────────────────────────────

class _FakeFreightExchangeEndpoints extends FreightExchangeEndpoints {
  _FakeFreightExchangeEndpoints()
      : super(ApiClient.create(
          baseUrl: 'https://test.com',
          getAccessToken: () async => null,
        ));

  List<FreightLoad> Function()? onListLoads;
  Map<String, dynamic> Function()? onImportLoad;
  Map<String, dynamic> Function()? onEvaluateLoad;

  String? lastListOrigin;
  String? lastListDestination;
  String? lastListDate;
  String? lastListCargoType;

  @override
  Future<List<FreightLoad>> listLoads({
    String? origin,
    String? destination,
    String? date,
    String? cargoType,
    int limit = 50,
    CancelToken? cancelToken,
  }) async {
    lastListOrigin = origin;
    lastListDestination = destination;
    lastListDate = date;
    lastListCargoType = cargoType;
    return onListLoads?.call() ?? [];
  }

  @override
  Future<Map<String, dynamic>> importLoad({
    required String providerId,
    required String loadId,
    CancelToken? cancelToken,
  }) async {
    return onImportLoad?.call() ?? {'status': 'imported'};
  }

  @override
  Future<Map<String, dynamic>> evaluateLoad({
    required String providerId,
    required String loadId,
    CancelToken? cancelToken,
  }) async {
    return onEvaluateLoad?.call() ?? {'score': 0.8};
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────

FreightLoad _dummyLoad({
  String id = '1',
  String providerId = 'p1',
  String providerLoadId = 'l1',
  String origin = 'A',
  String destination = 'B',
}) {
  return FreightLoad(
    id: id,
    providerId: providerId,
    providerLoadId: providerLoadId,
    origin: origin,
    destination: destination,
  );
}

ProviderContainer _createContainer({
  FreightExchangeEndpoints? endpoints,
}) {
  final container = ProviderContainer(
    overrides: [
      freightExchangeEndpointsProvider.overrideWithValue(
        endpoints ?? _FakeFreightExchangeEndpoints(),
      ),
    ],
  );
  return container;
}

void main() {
  // ==========================================================================
  // Provider chain tests
  // ==========================================================================
  group('freightExchangeEndpointsProvider', () {
    test('resolves to a FreightExchangeEndpoints instance', () {
      final container = _createContainer();
      final endpoints = container.read(freightExchangeEndpointsProvider);
      expect(endpoints, isA<FreightExchangeEndpoints>());
    });
  });

  group('freightExchangeStateProvider', () {
    test('initial state is FreightExchangeInitial', () {
      final container = _createContainer();
      final state = container.read(freightExchangeStateProvider);
      expect(state, isA<FreightExchangeInitial>());
    });
  });

  // ==========================================================================
  // FreightExchangeNotifier
  // ==========================================================================
  group('FreightExchangeNotifier', () {
    late _FakeFreightExchangeEndpoints fakeEndpoints;
    late FreightExchangeNotifier notifier;

    setUp(() {
      fakeEndpoints = _FakeFreightExchangeEndpoints();
      notifier = FreightExchangeNotifier(fakeEndpoints);
    });

    tearDown(() {
      notifier.dispose();
    });

    group('initial state', () {
      test('starts in FreightExchangeInitial', () {
        expect(notifier.state, isA<FreightExchangeInitial>());
      });
    });

    group('loadLoads', () {
      test('transitions to loading then data on success', () async {
        fakeEndpoints.onListLoads = () => [
              _dummyLoad(id: '1'),
              _dummyLoad(id: '2'),
            ];

        expect(notifier.state, isA<FreightExchangeInitial>());
        await notifier.loadLoads(origin: 'Bucharest');

        final state = notifier.state;
        expect(state, isA<FreightExchangeData>());
        expect((state as FreightExchangeData).loads.length, 2);
        expect(state.origin, 'Bucharest');
      });

      test('transitions to loading then error on failure', () async {
        fakeEndpoints.onListLoads = () => throw Exception('network');

        await notifier.loadLoads();

        expect(notifier.state, isA<FreightExchangeError>());
        expect(
          (notifier.state as FreightExchangeError).messageKey,
          'freightExchange_error',
        );
      });

      test('applies all filters', () async {
        await notifier.loadLoads(
          origin: 'Bucharest',
          destination: 'Cluj',
          date: '2026-09-15',
          cargoType: 'FTL',
        );

        expect(fakeEndpoints.lastListOrigin, 'Bucharest');
        expect(fakeEndpoints.lastListDestination, 'Cluj');
        expect(fakeEndpoints.lastListDate, '2026-09-15');
        expect(fakeEndpoints.lastListCargoType, 'FTL');
      });
    });

    group('refresh', () {
      test('delegates to loadLoads with same filters', () async {
        fakeEndpoints.onListLoads = () => [_dummyLoad(id: '1')];
        await notifier.loadLoads(origin: 'Bucharest');

        fakeEndpoints.onListLoads = () => [_dummyLoad(id: '2')];
        await notifier.refresh(origin: 'Bucharest');

        expect((notifier.state as FreightExchangeData).loads.first.id, '2');
      });
    });

    group('importLoad', () {
      test('calls endpoint and stays in data on success', () async {
        fakeEndpoints.onImportLoad = () => {'trip_id': 123};
        final load = _dummyLoad(providerId: 'timocom', providerLoadId: 'TL-001');
        notifier.state = FreightExchangeData(loads: [load]);

        await notifier.importLoad(load);

        expect(notifier.state, isA<FreightExchangeData>());
      });

      test('transitions to error on failure', () async {
        fakeEndpoints.onImportLoad = () => throw Exception('fail');
        final load = _dummyLoad();
        notifier.state = FreightExchangeData(loads: [load]);

        await notifier.importLoad(load);

        expect(notifier.state, isA<FreightExchangeError>());
      });

      test('does nothing when not in data state', () async {
        await notifier.importLoad(_dummyLoad());
        expect(notifier.state, isA<FreightExchangeInitial>());
      });
    });

    group('evaluateLoad', () {
      test('returns result on success', () async {
        fakeEndpoints.onEvaluateLoad = () => {'score': 0.9};
        final load = _dummyLoad();
        notifier.state = FreightExchangeData(loads: [load]);

        final result = await notifier.evaluateLoad(load);

        expect(result, isNotNull);
        expect(result!['score'], 0.9);
      });

      test('returns null and transitions to error on failure', () async {
        fakeEndpoints.onEvaluateLoad = () => throw Exception('fail');
        final load = _dummyLoad();
        notifier.state = FreightExchangeData(loads: [load]);

        final result = await notifier.evaluateLoad(load);

        expect(result, isNull);
        expect(notifier.state, isA<FreightExchangeError>());
      });

      test('does nothing when not in data state', () async {
        final result = await notifier.evaluateLoad(_dummyLoad());
        expect(result, isNull);
        expect(notifier.state, isA<FreightExchangeInitial>());
      });
    });
  });
}
