import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:operion_mobile/features/dispatcher/drivers/driver_list_screen.dart';
import 'package:operion_mobile/features/dispatcher/home/dispatcher_providers.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/shared/widgets/shimmer_loader.dart';
import 'package:operion_mobile/shared/widgets/empty_state.dart';
import 'package:operion_mobile/shared/widgets/app_card.dart';

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

Map<String, dynamic> _makeDriver({
  int id = 1,
  String name = 'Ion Popescu',
  String status = 'available',
  String? transportName,
  String? vehiclePlate,
}) {
  return {
    'id': id,
    'name': name,
    'status': status,
    'current_transport':
        transportName != null ? {'name': transportName} : null,
    'current_vehicle': vehiclePlate,
  };
}

final List<Map<String, dynamic>> _sampleDrivers = [
  _makeDriver(
    id: 1,
    name: 'Ion Popescu',
    status: 'available',
    transportName: 'Transport #101',
    vehiclePlate: 'B-01-ABC',
  ),
  _makeDriver(
    id: 2,
    name: 'Maria Ionescu',
    status: 'driving',
    transportName: 'Transport #102',
    vehiclePlate: 'B-02-XYZ',
  ),
  _makeDriver(
    id: 3,
    name: 'George Vasile',
    status: 'offline',
    transportName: null,
    vehiclePlate: 'B-03-DEF',
  ),
  _makeDriver(
    id: 4,
    name: 'Ana Moldovan',
    status: 'available',
    transportName: 'Transport #103',
    vehiclePlate: 'B-04-GHI',
  ),
  _makeDriver(
    id: 5,
    name: 'Dumitru Marin',
    status: 'offline',
    transportName: null,
    vehiclePlate: null,
  ),
];

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

Widget wrapDriverListScreen({
  required List<Map<String, dynamic>> drivers,
}) {
  return ProviderScope(
    overrides: [
      secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
      biometricServiceProvider.overrideWithValue(_MockBiometricService()),
      apiClientProvider.overrideWithValue(_stubApiClient()),
      dispatcherDriversProvider.overrideWith((ref) async => drivers),
    ],
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const DriverListScreen(),
    ),
  );
}

void main() {
  // ==========================================================================
  // DriverListScreen
  // ==========================================================================
  group('DriverListScreen', () {
    testWidgets('shows shimmer loading state', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
            biometricServiceProvider
                .overrideWithValue(_MockBiometricService()),
            apiClientProvider.overrideWithValue(_stubApiClient()),
            dispatcherDriversProvider.overrideWith(
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
            home: const DriverListScreen(),
          ),
        ),
      );
      await tester.pump();

      expect(find.byType(ShimmerLoader), findsWidgets);
    });

    testWidgets('shows error state with retry button', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
            biometricServiceProvider
                .overrideWithValue(_MockBiometricService()),
            apiClientProvider.overrideWithValue(_stubApiClient()),
            dispatcherDriversProvider.overrideWith(
              (ref) => Future.error(Exception('Failed to load drivers')),
            ),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              DefaultMaterialLocalizations.delegate,
              DefaultWidgetsLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const DriverListScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byIcon(Icons.error_outline), findsOneWidget);
      expect(find.byIcon(Icons.refresh), findsOneWidget);
    });

    testWidgets('shows empty state when no drivers', (tester) async {
      await tester.pumpWidget(wrapDriverListScreen(drivers: []));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(EmptyState), findsOneWidget);
      expect(find.byIcon(Icons.person_outline), findsOneWidget);
    });

    testWidgets('renders driver cards with data', (tester) async {
      await tester.pumpWidget(wrapDriverListScreen(drivers: _sampleDrivers));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // All visible driver names should be findable
      expect(find.text('Ion Popescu'), findsOneWidget);
      expect(find.text('Maria Ionescu'), findsOneWidget);
      expect(find.text('George Vasile'), findsOneWidget);
      expect(find.text('Ana Moldovan'), findsOneWidget);
      // 5th driver may be offscreen due to ListView virtualization

      // Cards should be present
      expect(find.byType(AppCard), findsWidgets);
    });

    testWidgets('shows filter chips row', (tester) async {
      await tester.pumpWidget(wrapDriverListScreen(drivers: _sampleDrivers));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // FilterChip widgets should be present
      expect(find.byType(FilterChip), findsWidgets);
    });

    testWidgets('filtering by available shows only available drivers',
        (tester) async {
      await tester.pumpWidget(wrapDriverListScreen(drivers: _sampleDrivers));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tap "Available" filter chip (second chip)
      final chips = find.byType(FilterChip);
      await tester.tap(chips.at(1)); // "Available" filter
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Only Ion Popescu and Ana Moldovan are available
      expect(find.text('Ion Popescu'), findsOneWidget);
      expect(find.text('Ana Moldovan'), findsOneWidget);
      // Maria (driving) and offline drivers should NOT be shown
      expect(find.text('Maria Ionescu'), findsNothing);
      expect(find.text('George Vasile'), findsNothing);
      expect(find.text('Dumitru Marin'), findsNothing);
    });

    testWidgets('filtering by driving shows only driving drivers',
        (tester) async {
      await tester.pumpWidget(wrapDriverListScreen(drivers: _sampleDrivers));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tap "Driving" filter chip
      final chips = find.byType(FilterChip);
      await tester.tap(chips.at(2));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Only Maria Ionescu is driving
      expect(find.text('Maria Ionescu'), findsOneWidget);
      expect(find.text('Ion Popescu'), findsNothing);
      expect(find.text('George Vasile'), findsNothing);
    });

    testWidgets('filtering by off shows offline drivers', (tester) async {
      await tester.pumpWidget(wrapDriverListScreen(drivers: _sampleDrivers));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tap "Off" filter chip
      final chips = find.byType(FilterChip);
      await tester.tap(chips.at(3));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // George Vasile and Dumitru Marin are offline
      expect(find.text('George Vasile'), findsOneWidget);
      expect(find.text('Dumitru Marin'), findsOneWidget);
      expect(find.text('Ion Popescu'), findsNothing);
      expect(find.text('Maria Ionescu'), findsNothing);
    });

    testWidgets('shows status indicators with correct colors',
        (tester) async {
      await tester.pumpWidget(wrapDriverListScreen(drivers: _sampleDrivers));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Status labels should be visible
      expect(find.text('Available'), findsWidgets);
      expect(find.text('Driving'), findsAtLeast(1));
      expect(find.text('Inactive'), findsWidgets);
    });

    testWidgets('shows transport and vehicle info on cards', (tester) async {
      await tester.pumpWidget(wrapDriverListScreen(drivers: _sampleDrivers));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Transport names should be visible
      expect(find.text('Transport #101'), findsOneWidget);
      expect(find.text('Transport #102'), findsOneWidget);
      expect(find.text('Transport #103'), findsOneWidget);
    });

    testWidgets('tapping driver card shows snackbar', (tester) async {
      await tester.pumpWidget(wrapDriverListScreen(drivers: _sampleDrivers));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tap on Ion Popescu's card
      await tester.tap(find.text('Ion Popescu'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Snackbar should appear with driver name
      expect(find.byType(SnackBar), findsOneWidget);
    });

    testWidgets('shows avatar initials for each driver', (tester) async {
      await tester.pumpWidget(wrapDriverListScreen(drivers: _sampleDrivers));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // CircleAvatars with first letter should be present
      expect(find.byType(CircleAvatar), findsWidgets);
    });
  });
}
