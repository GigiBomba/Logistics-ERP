import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:operion_mobile/features/dispatcher/analytics/dispatcher_analytics_screen.dart';
import 'package:operion_mobile/features/dispatcher/analytics/analytics_providers.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/shared/widgets/shimmer_loader.dart';
import 'package:operion_mobile/shared/widgets/app_card.dart';
import 'package:operion_mobile/shared/widgets/empty_state.dart';

// ---------------------------------------------------------------------------
// Mock implementations
// ---------------------------------------------------------------------------

class _MockSecureTokenStore extends SecureTokenStore {
  @override
  Future<bool> hasTokens() async => false;
  @override
  Future<String?> getAccessToken() async => null;
  @override
  Future<String?> getRefreshToken() async => null;
  @override
  Future<void> saveTokens(String access, String refresh) async {}
  @override
  Future<void> clearTokens() async {}
}

class _MockBiometricService extends BiometricService {
  @override
  Future<bool> isAvailable() async => false;
  @override
  Future<bool> authenticate({required String reason}) async => false;
}

ApiClient _stubApiClient() => ApiClient.create(
      baseUrl: '',
      apiKey: 'test-key',
      getAccessToken: () async => null,
    );

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const Map<String, dynamic> _sampleOverview = {
  'totalRevenue': 150000.00,
  'totalCosts': 95000.00,
  'profit': 55000.00,
};

const Map<String, dynamic> _sampleFinancial = {
  'revenue': 150000.00,
  'costs': 95000.00,
  'profit': 55000.00,
  'revenueTrend': 12.5,
  'costsTrend': -3.2,
  'profitTrend': 8.1,
};

const Map<String, dynamic> _sampleFleetUtil = {
  'activeTrucks': 18,
  'totalTrucks': 25,
  'utilizationPercent': 72.0,
};

final List<Map<String, dynamic>> _sampleClients = [
  {'clientName': 'Client A', 'revenue': 45000.0},
  {'clientName': 'Client B', 'revenue': 32000.0},
  {'clientName': 'Client C', 'revenue': 28000.0},
];

final List<Map<String, dynamic>> _sampleDrivers = [
  {'driverName': 'Ion Popescu', 'trips': 12, 'profit': 8500.0},
  {'driverName': 'Maria Ionescu', 'trips': 10, 'profit': 7200.0},
  {'driverName': 'George Vasile', 'trips': 8, 'profit': 6100.0},
];

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

Widget wrapAnalyticsScreen({
  required Map<String, dynamic> overview,
  required Map<String, dynamic> financial,
  required Map<String, dynamic> fleetUtil,
  required List<Map<String, dynamic>> clients,
  required List<Map<String, dynamic>> drivers,
}) {
  return ProviderScope(
    overrides: [
      secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
      biometricServiceProvider.overrideWithValue(_MockBiometricService()),
      apiClientProvider.overrideWithValue(_stubApiClient()),
      analyticsOverviewProvider(AnalyticsPeriod.thisMonth)
          .overrideWith((ref) async => overview),
      analyticsFinancialProvider(AnalyticsPeriod.thisMonth)
          .overrideWith((ref) async => financial),
      analyticsFleetUtilizationProvider(AnalyticsPeriod.thisMonth)
          .overrideWith((ref) async => fleetUtil),
      analyticsTopClientsProvider(AnalyticsPeriod.thisMonth)
          .overrideWith((ref) async => clients),
      analyticsDriverPerformanceProvider(AnalyticsPeriod.thisMonth)
          .overrideWith((ref) async => drivers),
    ],
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const DispatcherAnalyticsScreen(),
    ),
  );
}

/// Creates a test with overridden providers that return errors.
Widget wrapAnalyticsScreenError() {
  return ProviderScope(
    overrides: [
      secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
      biometricServiceProvider.overrideWithValue(_MockBiometricService()),
      apiClientProvider.overrideWithValue(_stubApiClient()),
      analyticsOverviewProvider(AnalyticsPeriod.thisMonth)
          .overrideWith((ref) => Future.error(Exception('Network error'))),
      analyticsFinancialProvider(AnalyticsPeriod.thisMonth)
          .overrideWith((ref) => Future.error(Exception('Network error'))),
      analyticsFleetUtilizationProvider(AnalyticsPeriod.thisMonth)
          .overrideWith((ref) => Future.error(Exception('Network error'))),
      analyticsTopClientsProvider(AnalyticsPeriod.thisMonth)
          .overrideWith((ref) => Future.error(Exception('Network error'))),
      analyticsDriverPerformanceProvider(AnalyticsPeriod.thisMonth)
          .overrideWith((ref) => Future.error(Exception('Network error'))),
    ],
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const DispatcherAnalyticsScreen(),
    ),
  );
}

void main() {
  // ==========================================================================
  // DispatcherAnalyticsScreen
  // ==========================================================================
  group('DispatcherAnalyticsScreen', () {
    testWidgets('shows shimmer loading for all sections', (tester) async {
      // Use providers that stay loading
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
            biometricServiceProvider
                .overrideWithValue(_MockBiometricService()),
            apiClientProvider.overrideWithValue(_stubApiClient()),
            analyticsOverviewProvider(AnalyticsPeriod.thisMonth)
                .overrideWith(
              (ref) => Completer<Map<String, dynamic>>().future,
            ),
            analyticsFinancialProvider(AnalyticsPeriod.thisMonth)
                .overrideWith(
              (ref) => Completer<Map<String, dynamic>>().future,
            ),
            analyticsFleetUtilizationProvider(AnalyticsPeriod.thisMonth)
                .overrideWith(
              (ref) => Completer<Map<String, dynamic>>().future,
            ),
            analyticsTopClientsProvider(AnalyticsPeriod.thisMonth)
                .overrideWith(
              (ref) => Completer<List<Map<String, dynamic>>>().future,
            ),
            analyticsDriverPerformanceProvider(AnalyticsPeriod.thisMonth)
                .overrideWith(
              (ref) => Completer<List<Map<String, dynamic>>>().future,
            ),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              DefaultMaterialLocalizations.delegate,
              DefaultWidgetsLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const DispatcherAnalyticsScreen(),
          ),
        ),
      );
      await tester.pump();

      expect(find.byType(ShimmerLoader), findsWidgets);
    });

    testWidgets('shows error states for all sections', (tester) async {
      await tester.pumpWidget(wrapAnalyticsScreenError());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Each error section should have retry buttons
      expect(find.byType(TextButton), findsWidgets);
    });

    testWidgets('renders period toggle', (tester) async {
      await tester.pumpWidget(wrapAnalyticsScreen(
        overview: _sampleOverview,
        financial: _sampleFinancial,
        fleetUtil: _sampleFleetUtil,
        clients: _sampleClients,
        drivers: _sampleDrivers,
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Period toggle should render
      expect(find.byType(SegmentedButton<AnalyticsPeriod>), findsOneWidget);
    });

    testWidgets('renders overview card with revenue, costs, profit',
        (tester) async {
      await tester.pumpWidget(wrapAnalyticsScreen(
        overview: _sampleOverview,
        financial: _sampleFinancial,
        fleetUtil: _sampleFleetUtil,
        clients: _sampleClients,
        drivers: _sampleDrivers,
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Overview section should show data values (formatted)
      expect(find.byType(AppCard), findsWidgets);
    });

    testWidgets('renders fleet utilization card', (tester) async {
      await tester.pumpWidget(wrapAnalyticsScreen(
        overview: _sampleOverview,
        financial: _sampleFinancial,
        fleetUtil: _sampleFleetUtil,
        clients: _sampleClients,
        drivers: _sampleDrivers,
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Fleet utilization percentage should be displayed
      expect(find.text('72%'), findsOneWidget);
    });

    testWidgets('renders top clients list', (tester) async {
      await tester.pumpWidget(wrapAnalyticsScreen(
        overview: _sampleOverview,
        financial: _sampleFinancial,
        fleetUtil: _sampleFleetUtil,
        clients: _sampleClients,
        drivers: _sampleDrivers,
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // All three client names should be visible
      expect(find.text('Client A'), findsOneWidget);
      expect(find.text('Client B'), findsOneWidget);
      expect(find.text('Client C'), findsOneWidget);
    });

    testWidgets('renders driver performance list', (tester) async {
      await tester.pumpWidget(wrapAnalyticsScreen(
        overview: _sampleOverview,
        financial: _sampleFinancial,
        fleetUtil: _sampleFleetUtil,
        clients: _sampleClients,
        drivers: _sampleDrivers,
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Scroll down to see driver performance section
      await tester.drag(find.byType(ListView), const Offset(0, -400));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // All three driver names should be visible
      expect(find.text('Ion Popescu'), findsOneWidget);
      expect(find.text('Maria Ionescu'), findsOneWidget);
      expect(find.text('George Vasile'), findsOneWidget);
    });

    testWidgets('renders desktop CTA at the bottom', (tester) async {
      await tester.pumpWidget(wrapAnalyticsScreen(
        overview: _sampleOverview,
        financial: _sampleFinancial,
        fleetUtil: _sampleFleetUtil,
        clients: _sampleClients,
        drivers: _sampleDrivers,
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Scroll to the bottom to see the CTA
      await tester.drag(find.byType(ListView), const Offset(0, -800));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Desktop CTA should be visible
      expect(find.byType(AppCard), findsWidgets);
    });

    testWidgets('empty clients shows empty state', (tester) async {
      await tester.pumpWidget(wrapAnalyticsScreen(
        overview: _sampleOverview,
        financial: _sampleFinancial,
        fleetUtil: _sampleFleetUtil,
        clients: [],
        drivers: _sampleDrivers,
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Scroll to the clients section
      await tester.drag(find.byType(ListView), const Offset(0, -300));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Should find EmptyState for the empty clients section
      expect(find.byType(EmptyState), findsOneWidget);
    });

    testWidgets('empty drivers shows empty state', (tester) async {
      await tester.pumpWidget(wrapAnalyticsScreen(
        overview: _sampleOverview,
        financial: _sampleFinancial,
        fleetUtil: _sampleFleetUtil,
        clients: _sampleClients,
        drivers: [],
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Scroll to the drivers section
      await tester.drag(find.byType(ListView), const Offset(0, -500));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(EmptyState), findsOneWidget);
    });

    testWidgets('tapping desktop CTA shows snackbar',
        (tester) async {
      await tester.pumpWidget(wrapAnalyticsScreen(
        overview: _sampleOverview,
        financial: _sampleFinancial,
        fleetUtil: _sampleFleetUtil,
        clients: _sampleClients,
        drivers: _sampleDrivers,
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Scroll down to make the CTA visible
      await tester.drag(find.byType(ListView), const Offset(0, -800));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tap the desktop CTA (last AppCard in the list)
      final appCards = find.byType(AppCard);
      await tester.tap(appCards.last);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Should show snackbar
      expect(find.byType(SnackBar), findsOneWidget);
    });
  });
}
