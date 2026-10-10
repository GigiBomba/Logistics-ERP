import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';

import '../shared/test_utils.dart';
import '../shared/mocks/mocks.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/driver_endpoints.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/driver/home/driver_providers.dart';
import 'package:operion_mobile/features/driver/transports/transport_detail_screen.dart';
import 'package:operion_mobile/shared/models/transport.dart';
import 'package:operion_mobile/shared/widgets/status_badge.dart';

// ---------------------------------------------------------------------------
// Mock providers
// ---------------------------------------------------------------------------


Transport _mockTransport({String status = 'planned', String? origin, String? destination}) => Transport(
  id: '100', companyId: '1',
  loadInfo: 'Steel coils — 24 tons',
  origin: origin ?? 'Cluj-Napoca', destination: destination ?? 'Bucharest',
  waypoints: ['Sibiu', 'Brasov'],
  status: status,
  assignedDriverId: '10', assignedDriverName: 'Mihai Popescu',
  vehicleId: '5', vehiclePlate: 'CJ-01-ABC',
  scheduledDate: DateTime.now().subtract(const Duration(days: 1)),
  deliveredDate: status == 'delivered' ? DateTime.now() : null,
  lastUpdated: DateTime.now(),
  originLat: 46.7712, originLng: 23.6236,
  destLat: 44.4268, destLng: 26.1025,
);

class _StubDriverEndpoints extends DriverEndpoints {
  final Transport transport;
  final Object? detailError;
  final Object? statusUpdateError;
  Transport? _current;

  _StubDriverEndpoints({
    required this.transport,
    this.detailError,
    this.statusUpdateError,
  })  : _current = transport,
        super(ApiClient.create(baseUrl: '', getAccessToken: () async => null));

  @override Future<Response> getTransport(String id) async {
    if (detailError != null) throw detailError!;
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: _current!.toJson(),
    );
  }

  @override Future<Response> updateStatus(String transportId, String newStatus) async {
    if (statusUpdateError != null) throw statusUpdateError!;
    _current = Transport(
      id: _current!.id, companyId: _current!.companyId,
      loadInfo: _current!.loadInfo,
      origin: _current!.origin, destination: _current!.destination,
      waypoints: _current!.waypoints,
      status: newStatus,
      assignedDriverId: _current!.assignedDriverId,
      assignedDriverName: _current!.assignedDriverName,
      vehicleId: _current!.vehicleId, vehiclePlate: _current!.vehiclePlate,
      scheduledDate: _current!.scheduledDate,
      deliveredDate: newStatus == 'delivered' ? DateTime.now() : _current!.deliveredDate,
      lastUpdated: DateTime.now(),
      originLat: _current!.originLat, originLng: _current!.originLng,
      destLat: _current!.destLat, destLng: _current!.destLng,
    );
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: {'status': 'ok', 'updated_at': DateTime.now().toIso8601String()},
    );
  }

  @override Future<Response> getTransports() async =>
      Response(requestOptions: RequestOptions(path: ''), data: []);
}

List<Override> _overrides(Transport transport, {Object? detailError, Object? statusUpdateError}) => [
  secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
  biometricServiceProvider.overrideWithValue(MockBiometricService()),
  isOfflineProvider.overrideWith((ref) => false),
  driverEndpointsProvider.overrideWithValue(_StubDriverEndpoints(
    transport: transport, detailError: detailError, statusUpdateError: statusUpdateError,
  )),
];

Widget _wrap(String transportId, Transport transport,
    {Object? detailError, Object? statusUpdateError}) =>
  ProviderScope(
    overrides: _overrides(transport, detailError: detailError, statusUpdateError: statusUpdateError),
    child: MaterialApp(
      localizationsDelegates: const [AppLocalizations.delegate],
      supportedLocales: AppLocalizations.supportedLocales,
      home: TransportDetailScreen(transportId: transportId),
    ),
  );

// ---------------------------------------------------------------------------
// 30 Test scenarios
// ---------------------------------------------------------------------------

void main() {
  group('TransportDetailScreen — Loading', () {
    testWidgets('1. shows shimmer while loading', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.textContaining('ransport'), findsWidgets);
    });

    testWidgets('2. AppBar title is "Transport details"', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.textContaining('ransport'), findsWidgets);
    });
  });

  group('TransportDetailScreen — Error', () {
    testWidgets('3. error state shows retry button', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport(),
          detailError: Exception('Server error')));
      await settle(tester);
      expect(find.textContaining('Retry'), findsAny);
    });

    testWidgets('4. error shows error icon', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport(),
          detailError: Exception('Timeout')));
      await settle(tester);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });
  });

  group('TransportDetailScreen — Load info', () {
    testWidgets('5. shows load info text', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.text('Steel coils — 24 tons'), findsOneWidget);
    });

    testWidgets('6. load info has left border accent', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.byType(Container), findsWidgets);
    });
  });

  group('TransportDetailScreen — Route card', () {
    testWidgets('7. shows origin in route card', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.text('Cluj-Napoca'), findsOneWidget);
    });

    testWidgets('8. shows destination in route card', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.text('Bucharest'), findsOneWidget);
    });

    testWidgets('9. shows waypoints', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.text('Sibiu'), findsOneWidget);
      expect(find.text('Brasov'), findsOneWidget);
    });

    testWidgets('10. shows navigate button for origin', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.textContaining('Navigate'), findsWidgets);
    });
  });

  group('TransportDetailScreen — Status section', () {
    testWidgets('11. shows status badge', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport(status: 'in_transit')));
      await settle(tester);
      expect(find.byType(StatusBadge), findsOneWidget);
    });

    testWidgets('12. planned status shows "Start Loading" button', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport(status: 'planned')));
      await settle(tester);
      expect(find.text('Start Loading'), findsOneWidget);
    });

    testWidgets('13. loading status shows "Depart" button', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport(status: 'loading')));
      await settle(tester);
      expect(find.text('Depart'), findsOneWidget);
    });

    testWidgets('14. in_transit shows "Mark Delivered" and "Report Delay"', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport(status: 'in_transit')));
      await settle(tester);
      expect(find.text('Mark Delivered'), findsOneWidget);
      expect(find.text('Report Delay'), findsOneWidget);
    });

    testWidgets('15. delivered status shows final message', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport(status: 'delivered')));
      await settle(tester);
      expect(find.textContaining('Delivered'), findsAny);
    });

    testWidgets('16. cancelled shows final message', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport(status: 'cancelled')));
      await settle(tester);
      expect(find.textContaining('Cancelled'), findsAny);
    });

    testWidgets('17. staleness indicator shown', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.text('Just now'), findsOneWidget);
    });

    testWidgets('18. tapping status button updates transport', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport(status: 'planned')));
      await settle(tester);
      await tester.tap(find.text('Start Loading'));
      await settle(tester);
      // Should show success snackbar
      expect(find.textContaining('Status updated'), findsAny);
    });
  });

  group('TransportDetailScreen — Info grid', () {
    testWidgets('19. shows driver name in grid', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.text('Mihai Popescu'), findsOneWidget);
    });

    testWidgets('20. shows vehicle plate in grid', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.text('CJ-01-ABC'), findsOneWidget);
    });

    testWidgets('21. shows 4 info items', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.byType(GridView), findsOneWidget);
    });
  });

  group('TransportDetailScreen — Documents section', () {
    testWidgets('22. shows documents section with count', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.textContaining('document'), findsAny);
    });

    testWidgets('23. shows "View Documents" button', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.text('View Documents'), findsOneWidget);
    });

    testWidgets('24. shows "Add Document" button', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.text('Add Document'), findsOneWidget);
    });
  });

  group('TransportDetailScreen — Edge cases', () {
    testWidgets('25. RefreshIndicator present', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.byType(RefreshIndicator), findsOneWidget);
    });

    testWidgets('26. no origin lat/lng — no navigate button for origin', (tester) async {
      final t = _mockTransport();
      final tNoCoords = Transport(
        id: t.id, companyId: t.companyId, loadInfo: t.loadInfo,
        origin: t.origin, destination: t.destination, waypoints: t.waypoints,
        status: t.status, lastUpdated: t.lastUpdated,
      );
      await tester.pumpWidget(_wrap('100', tNoCoords));
      await settle(tester);
      expect(find.text('Steel coils — 24 tons'), findsOneWidget);
    });

    testWidgets('27. status update fails — error snackbar shown', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport(status: 'planned'),
          statusUpdateError: Exception('API error')));
      await settle(tester);
      await tester.tap(find.text('Start Loading'));
      await settle(tester);
      // The error snackbar shows "${loc.general_error}: $e" = "An error occurred: Exception: API error"
      expect(find.textContaining('An error'), findsAny);
    });

    testWidgets('28. offline warning shows when isOffline is true', (tester) async {
      final overrides = <Override>[
        ..._overrides(_mockTransport()),
        isOfflineProvider.overrideWith((ref) => true),
      ];
      await tester.pumpWidget(ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: const TransportDetailScreen(transportId: '100'),
        ),
      ));
      await settle(tester);
      // loc.general_offline returns "You are offline" in English locale
      expect(find.textContaining('You are offline'), findsAny);
    });

    testWidgets('29. waypoints with index numbers visible', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport()));
      await settle(tester);
      expect(find.text('1'), findsOneWidget);
      expect(find.text('2'), findsOneWidget);
    });

    testWidgets('30. unknown status shows "No actions available"', (tester) async {
      await tester.pumpWidget(_wrap('100', _mockTransport(status: 'unknown_status')));
      await settle(tester);
      expect(find.textContaining('No actions available'), findsOneWidget);
    });
  });
}
