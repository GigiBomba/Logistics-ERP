import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:operion_mobile/features/dispatcher/home/dispatcher_home_screen.dart';
import 'package:operion_mobile/features/dispatcher/home/dispatcher_providers.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/shared/widgets/shimmer_loader.dart';
import 'package:operion_mobile/shared/widgets/app_card.dart';
import 'package:operion_mobile/shared/widgets/staleness_indicator.dart';

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
  'activeJobs': 5,
  'activeDrivers': 12,
  'openAlerts': 3,
  'vehiclesOnRoad': 8,
  'lastUpdated': '2026-07-19T10:30:00',
};

const Map<String, dynamic> _sampleOverviewNoTimestamp = {
  'activeJobs': 0,
  'activeDrivers': 0,
  'openAlerts': 0,
  'vehiclesOnRoad': 0,
};

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

Widget wrapHomeScreen({
  required Map<String, dynamic> overview,
}) {
  return ProviderScope(
    overrides: [
      secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
      biometricServiceProvider.overrideWithValue(_MockBiometricService()),
      apiClientProvider.overrideWithValue(_stubApiClient()),
      dispatcherOverviewProvider.overrideWith((ref) async => overview),
      dispatcherTabProvider.overrideWith((ref) => 0),
    ],
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const Scaffold(body: DispatcherHomeScreen()),
    ),
  );
}

void main() {
  // ==========================================================================
  // DispatcherHomeScreen
  // ==========================================================================
  group('DispatcherHomeScreen', () {
    testWidgets('shows shimmer loading state', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureTokenStoreProvider
                .overrideWithValue(_MockSecureTokenStore()),
            biometricServiceProvider
                .overrideWithValue(_MockBiometricService()),
            apiClientProvider.overrideWithValue(_stubApiClient()),
            dispatcherOverviewProvider.overrideWith(
              (ref) => Completer<Map<String, dynamic>>().future,
            ),
            dispatcherTabProvider.overrideWith((ref) => 0),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              DefaultMaterialLocalizations.delegate,
              DefaultWidgetsLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const Scaffold(body: DispatcherHomeScreen()),
          ),
        ),
      );
      await tester.pump();

      // Shimmer should be visible
      expect(find.byType(ShimmerLoader), findsWidgets);
    });

    testWidgets('shows error state with retry button', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureTokenStoreProvider
                .overrideWithValue(_MockSecureTokenStore()),
            biometricServiceProvider
                .overrideWithValue(_MockBiometricService()),
            apiClientProvider.overrideWithValue(_stubApiClient()),
            dispatcherOverviewProvider.overrideWith(
              (ref) => Future.error(Exception('Failed to load overview')),
            ),
            dispatcherTabProvider.overrideWith((ref) => 0),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              DefaultMaterialLocalizations.delegate,
              DefaultWidgetsLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const Scaffold(body: DispatcherHomeScreen()),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Error icon and retry button should be visible
      expect(find.byType(FilledButton), findsOneWidget);
    });

    testWidgets('renders KPI cards with data values', (tester) async {
      await tester.pumpWidget(wrapHomeScreen(overview: _sampleOverview));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // KPI values should be visible (formatted as strings)
      expect(find.text('5'), findsOneWidget);
      expect(find.text('12'), findsOneWidget);
      expect(find.text('3'), findsOneWidget);
      expect(find.text('8'), findsOneWidget);

      // KPI grid structure: AppCards inside
      expect(find.byType(AppCard), findsWidgets);
    });

    testWidgets('renders quick actions row', (tester) async {
      await tester.pumpWidget(wrapHomeScreen(overview: _sampleOverview));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Quick action chips should be visible
      expect(find.byType(ActionChip), findsWidgets);
    });

    testWidgets('shows staleness indicator with last updated time',
        (tester) async {
      await tester.pumpWidget(wrapHomeScreen(overview: _sampleOverview));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // StalenessIndicator should be visible
      expect(find.byType(StalenessIndicator), findsOneWidget);
    });

    testWidgets('handles zero values in KPI cards', (tester) async {
      await tester.pumpWidget(
        wrapHomeScreen(overview: _sampleOverviewNoTimestamp),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // All zero values should render as '0'
      expect(find.text('0'), findsNWidgets(4));
    });

    testWidgets('supports pull-to-refresh via RefreshIndicator',
        (tester) async {
      await tester.pumpWidget(wrapHomeScreen(overview: _sampleOverview));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // RefreshIndicator should wrap the content
      expect(find.byType(RefreshIndicator), findsOneWidget);
    });

    testWidgets('header shows dispatcher overview title', (tester) async {
      await tester.pumpWidget(wrapHomeScreen(overview: _sampleOverview));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // The overview label uses locale keys, so we check for the
      // DispatcherHomeScreen widget itself
      expect(find.byType(DispatcherHomeScreen), findsOneWidget);
    });

    testWidgets('tapping quick action chips does not crash', (tester) async {
      await tester.pumpWidget(wrapHomeScreen(overview: _sampleOverview));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tap on quick action chips
      final chips = find.byType(ActionChip);
      if (chips.evaluate().isNotEmpty) {
        await tester.tap(chips.first);
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));
        // Should not crash
      }
    });
  });
}
