import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../shared/test_utils.dart';
import '../../../shared/mocks/mocks.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/driver_endpoints.dart';
import 'package:operion_mobile/core/providers/driver_providers.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/driver/models/driver_trip_overview.dart';
import 'package:operion_mobile/features/driver/trip_overview/screens/driver_trip_overview_screen.dart';
import 'package:operion_mobile/features/driver/trip_overview/providers/trip_overview_providers.dart';
import 'package:operion_mobile/features/driver/trip_overview/providers/trip_overview_state.dart';
import 'package:operion_mobile/shared/widgets/shimmer_loader.dart';
import 'package:operion_mobile/shared/widgets/staleness_indicator.dart';
import 'package:operion_mobile/shared/widgets/empty_state.dart';
import 'package:operion_mobile/shared/widgets/status_badge.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------


class _StubDriverEndpoints extends DriverEndpoints {
  _StubDriverEndpoints()
      : super(ApiClient.create(
          baseUrl: '',
          getAccessToken: () async => null,
        ));

  @override
  Future<Response> updateStatus(String transportId, String status) async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: {'status': 'ok'},
    );
  }
}

DriverTripOverview _overview({
  String? transportId = 'T-123',
  String? loadInfo = 'Electronics shipment',
  String? origin = 'Warehouse A',
  String? destination = 'Store B',
  TripStatus? status = TripStatus.inTransit,
  DateTime? statusSince,
  DateTime? eta,
  EtaConfidence etaConfidence = EtaConfidence.live,
}) {
  return DriverTripOverview(
    transportId: transportId,
    loadInfo: loadInfo,
    origin: origin,
    destination: destination,
    status: status,
    statusSince: statusSince ?? DateTime.now().subtract(const Duration(hours: 2)),
    eta: eta ?? DateTime.now().add(const Duration(hours: 3)),
    etaConfidence: etaConfidence,
  );
}

/// Base overrides used in all tests.
/// Provides a silent single-value stream for the elapsed timer to avoid
/// hanging [pumpAndSettle] on periodic timers.
List<Override> _baseOverrides(DriverTripOverview overview, {bool isOffline = false}) => [
  secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
  biometricServiceProvider.overrideWithValue(MockBiometricService()),
  isOfflineProvider.overrideWith((ref) => isOffline),
  driverEndpointsProvider.overrideWithValue(_StubDriverEndpoints()),
  tripOverviewProvider.overrideWithProvider(
    FutureProvider<DriverTripOverview>((ref) async => overview),
  ),
  elapsedTimerProvider.overrideWithProvider(
    StreamProvider<void>((ref) => Stream.value(null)),
  ),
];

Widget _wrap(DriverTripOverview overview, {bool isOffline = false}) {
  return ProviderScope(
    overrides: _baseOverrides(overview, isOffline: isOffline),
    child: MaterialApp(
      localizationsDelegates: const [AppLocalizations.delegate],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const DriverTripOverviewScreen(),
    ),
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  group('DriverTripOverviewScreen — Loading', () {
    testWidgets('shows shimmer during loading', (tester) async {
      // Use a provider that never completes to keep the loading state visible.
      final completer = Completer<DriverTripOverview>();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
            biometricServiceProvider.overrideWithValue(MockBiometricService()),
            tripOverviewProvider.overrideWithProvider(
              FutureProvider<DriverTripOverview>((ref) => completer.future),
            ),
            elapsedTimerProvider.overrideWithProvider(
              StreamProvider<void>((ref) => Stream.value(null)),
            ),
          ],
          child: MaterialApp(
            localizationsDelegates: const [AppLocalizations.delegate],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const DriverTripOverviewScreen(),
          ),
        ),
      );
      await tester.pump();
      expect(find.byType(ShimmerLoader), findsWidgets);
    });
  });

  group('DriverTripOverviewScreen — Error', () {
    testWidgets('shows retry button on error', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
            biometricServiceProvider.overrideWithValue(MockBiometricService()),
            tripOverviewProvider.overrideWithProvider(
              FutureProvider<DriverTripOverview>((ref) => throw Exception('Network error')),
            ),
            elapsedTimerProvider.overrideWithProvider(
              StreamProvider<void>((ref) => Stream.value(null)),
            ),
          ],
          child: MaterialApp(
            localizationsDelegates: const [AppLocalizations.delegate],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const DriverTripOverviewScreen(),
          ),
        ),
      );
      await settle(tester);
      // Retry button should be visible (loc.general_retry = 'Retry' in English)
      expect(find.text('Retry'), findsOneWidget);
      // Error icon (alertCircle) should be present
      expect(find.byIcon(LucideIcons.alertCircle), findsOneWidget);
    });
  });

  group('DriverTripOverviewScreen — Empty (no active trip)', () {
    testWidgets('shows empty state when transportId is null', (tester) async {
      final emptyOverview = _overview(transportId: null, loadInfo: null, origin: null, destination: null, status: null, statusSince: null, eta: null, etaConfidence: EtaConfidence.unavailable);
      await tester.pumpWidget(_wrap(emptyOverview));
      await settle(tester);
      expect(find.byType(EmptyState), findsOneWidget);
      expect(find.text('No active trip'), findsOneWidget);
      expect(find.text('You have no transport assigned at this time.'), findsOneWidget);
    });
  });

  group('DriverTripOverviewScreen — Data with live ETA', () {
    testWidgets('shows transport summary card with status badge', (tester) async {
      final overview = _overview();
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      expect(find.byType(StatusBadge), findsOneWidget);
      expect(find.text('Electronics shipment'), findsOneWidget);
    });

    testWidgets('shows origin and destination', (tester) async {
      final overview = _overview();
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      // The text is rendered as "Warehouse A → Store B"
      expect(find.textContaining('Warehouse A'), findsOneWidget);
      expect(find.textContaining('Store B'), findsOneWidget);
    });

    testWidgets('shows live ETA value', (tester) async {
      final eta = DateTime(2026, 7, 19, 14, 30);
      final overview = _overview(eta: eta, etaConfidence: EtaConfidence.live);
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      // ETA formatted as HH:MM
      expect(find.text('14:30'), findsOneWidget);
    });

    testWidgets('shows elapsed time', (tester) async {
      final statusSince = DateTime.now().subtract(const Duration(hours: 2, minutes: 15));
      final overview = _overview(statusSince: statusSince);
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      // Should show something like "2h 15m"
      expect(find.textContaining('15m'), findsOneWidget);
    });

    testWidgets('shows status action buttons for non-terminal status', (tester) async {
      final overview = _overview(status: TripStatus.inTransit);
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      // in_transit status should show "Mark Delivered" and "Report Delay"
      expect(find.text('Mark Delivered'), findsOneWidget);
      expect(find.text('Report Delay'), findsOneWidget);
    });

    testWidgets('does not show status actions for terminal status (delivered)', (tester) async {
      final overview = _overview(status: TripStatus.delivered);
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      // No status action buttons should appear
      expect(find.text('Mark Delivered'), findsNothing);
    });

    testWidgets('shows offline warning when isOffline is true', (tester) async {
      final overview = _overview(status: TripStatus.inTransit);
      await tester.pumpWidget(_wrap(overview, isOffline: true));
      await settle(tester);
      expect(find.textContaining('You are offline'), findsAny);
    });

    testWidgets('RefreshIndicator is present', (tester) async {
      final overview = _overview();
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      expect(find.byType(RefreshIndicator), findsOneWidget);
    });
  });

  group('DriverTripOverviewScreen — Data with stale ETA', () {
    testWidgets('shows StalenessIndicator when ETA is stale', (tester) async {
      final overview = _overview(etaConfidence: EtaConfidence.stale);
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      expect(find.byType(StalenessIndicator), findsOneWidget);
    });

    testWidgets('does not show StalenessIndicator when ETA is live', (tester) async {
      final overview = _overview(etaConfidence: EtaConfidence.live);
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      expect(find.byType(StalenessIndicator), findsNothing);
    });

    testWidgets('shows stale ETA in warning color', (tester) async {
      final eta = DateTime(2026, 7, 19, 16, 00);
      final overview = _overview(eta: eta, etaConfidence: EtaConfidence.stale);
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      expect(find.text('16:00'), findsOneWidget);
    });
  });

  group('DriverTripOverviewScreen — ETA unavailable', () {
    testWidgets('shows unavailable message', (tester) async {
      final overview = _overview(eta: null, etaConfidence: EtaConfidence.unavailable);
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      expect(find.text('ETA unavailable'), findsOneWidget);
    });
  });

  group('DriverTripOverviewScreen — Status update actions', () {
    testWidgets('planned status shows "Start Loading" button', (tester) async {
      final overview = _overview(status: TripStatus.planned);
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      expect(find.text('Start Loading'), findsOneWidget);
    });

    testWidgets('loading status shows "Depart" button', (tester) async {
      final overview = _overview(status: TripStatus.loading);
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      expect(find.text('Depart'), findsOneWidget);
    });

    testWidgets('inTransit status shows both action buttons', (tester) async {
      final overview = _overview(status: TripStatus.inTransit);
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      expect(find.text('Mark Delivered'), findsOneWidget);
      expect(find.text('Report Delay'), findsOneWidget);
    });

    testWidgets('delivered status shows no action buttons', (tester) async {
      final overview = _overview(status: TripStatus.delivered);
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      expect(find.text('Start Loading'), findsNothing);
      expect(find.text('Mark Delivered'), findsNothing);
    });

    testWidgets('cancelled status shows no action buttons', (tester) async {
      final overview = _overview(status: TripStatus.cancelled);
      await tester.pumpWidget(_wrap(overview));
      await settle(tester);
      expect(find.text('Start Loading'), findsNothing);
    });
  });
}
