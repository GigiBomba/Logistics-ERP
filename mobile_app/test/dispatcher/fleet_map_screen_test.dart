import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_map/flutter_map.dart';

import 'package:operion_mobile/features/dispatcher/fleet/fleet_map_screen.dart';
import 'package:operion_mobile/features/dispatcher/home/dispatcher_providers.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/shared/models/fleet_position.dart';
import 'package:operion_mobile/shared/widgets/shimmer_loader.dart';

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

final _now = DateTime.now();

final List<FleetPosition> _samplePositions = [
  FleetPosition(
    vehicleId: 'v1',
    plate: 'B-01-ABC',
    driverName: 'Ion Popescu',
    latitude: 44.439663,
    longitude: 26.096306,
    status: 'active',
    lastUpdate: _now.subtract(const Duration(minutes: 5)),
  ),
  FleetPosition(
    vehicleId: 'v2',
    plate: 'B-02-XYZ',
    driverName: 'Maria Ionescu',
    latitude: 45.943161,
    longitude: 24.966076,
    status: 'stopped',
    lastUpdate: _now.subtract(const Duration(minutes: 15)),
  ),
  FleetPosition(
    vehicleId: 'v3',
    plate: 'B-03-DEF',
    driverName: 'George Vasile',
    latitude: 46.77121,
    longitude: 23.62363,
    status: 'idle',
    lastUpdate: _now.subtract(const Duration(minutes: 45)),
  ),
  // Vehicle with sentinel (0,0) coordinates that should be filtered out
  FleetPosition(
    vehicleId: 'v4',
    plate: 'B-00-SEN',
    driverName: 'Sentinel',
    latitude: 0.0,
    longitude: 0.0,
    status: 'offline',
    lastUpdate: _now,
  ),
];

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

Widget wrapFleetMapScreen({
  required List<FleetPosition> positions,
  bool isOffline = false,
}) {
  return ProviderScope(
    overrides: [
      secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
      biometricServiceProvider.overrideWithValue(_MockBiometricService()),
      apiClientProvider.overrideWithValue(_stubApiClient()),
      fleetPositionsProvider.overrideWith((ref) async => positions),
      isOfflineProvider.overrideWith((ref) => isOffline),
    ],
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const FleetMapScreen(),
    ),
  );
}

void main() {
  // ==========================================================================
  // FleetMapScreen
  // ==========================================================================
  group('FleetMapScreen', () {
    testWidgets('shows shimmer loading state', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
            biometricServiceProvider
                .overrideWithValue(_MockBiometricService()),
            apiClientProvider.overrideWithValue(_stubApiClient()),
            fleetPositionsProvider.overrideWith(
              (ref) => Completer<List<FleetPosition>>().future,
            ),
            isOfflineProvider.overrideWith((ref) => false),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              DefaultMaterialLocalizations.delegate,
              DefaultWidgetsLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const FleetMapScreen(),
          ),
        ),
      );
      await tester.pump();

      expect(find.byType(ShimmerLoader), findsOneWidget);
    });

    testWidgets('shows error state with retry button', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
            biometricServiceProvider
                .overrideWithValue(_MockBiometricService()),
            apiClientProvider.overrideWithValue(_stubApiClient()),
            fleetPositionsProvider.overrideWith(
              (ref) => Future.error(Exception('Failed to load fleet data')),
            ),
            isOfflineProvider.overrideWith((ref) => false),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              DefaultMaterialLocalizations.delegate,
              DefaultWidgetsLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const FleetMapScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Error view with retry button should be visible
      expect(find.byType(FilledButton), findsOneWidget);
    });

    testWidgets('renders map view when positions loaded', (tester) async {
      await tester.pumpWidget(
        wrapFleetMapScreen(positions: _samplePositions),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // FlutterMap should be present
      expect(find.byType(FlutterMap), findsOneWidget);

      // RefreshIndicator should wrap the content
      expect(find.byType(RefreshIndicator), findsOneWidget);
    });

    testWidgets('shows map when offline (no crash)', (tester) async {
      await tester.pumpWidget(
        wrapFleetMapScreen(positions: _samplePositions, isOffline: true),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // Map should still render
      expect(find.byType(FlutterMap), findsOneWidget);
    });

    testWidgets('shows RefreshIndicator for pull-to-refresh', (tester) async {
      await tester.pumpWidget(
        wrapFleetMapScreen(positions: _samplePositions),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // RefreshIndicator should be present
      expect(find.byType(RefreshIndicator), findsOneWidget);
    });
  });
}
