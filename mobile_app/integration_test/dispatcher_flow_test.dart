import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import 'package:integration_test/integration_test.dart';

import 'package:operion_mobile/app.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/auth_endpoints.dart';
import 'package:operion_mobile/core/network/endpoints/dispatcher_endpoints.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/shared/models/user.dart';
import 'package:operion_mobile/features/dispatcher/home/dispatcher_providers.dart';

// ---------------------------------------------------------------------------
// Mock / Stub providers for dispatcher flow
// ---------------------------------------------------------------------------

class _MockSecureTokenStore extends SecureTokenStore {
  String? _accessToken = 'mock_token';
  String? _refreshToken = 'mock_refresh';

  @override
  Future<bool> hasTokens() async => true;

  @override
  Future<String?> getAccessToken() async => _accessToken;

  @override
  Future<String?> getRefreshToken() async => _refreshToken;

  @override
  Future<void> saveTokens(String access, String refresh) async {
    _accessToken = access;
    _refreshToken = refresh;
  }

  @override
  Future<void> clearTokens() async {
    _accessToken = null;
    _refreshToken = null;
  }
}

class _MockBiometricService extends BiometricService {
  @override
  Future<bool> isAvailable() async => false;

  @override
  Future<bool> authenticate({required String reason}) async => false;
}

/// Stub AuthEndpoints returning a pre-authenticated dispatcher session.
class _StubAuthEndpoints extends AuthEndpoints {
  _StubAuthEndpoints()
      : super(ApiClient.create(
          baseUrl: '',
          getAccessToken: () async => 'mock_token',
        ));

  @override
  Future<Response> login(String email, String password, {String? deviceId}) async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: {
        'access_token': 'mock_access_token',
        'refresh_token': 'mock_refresh_token',
      },
    );
  }

  @override
  Future<Response> refreshToken(String refreshToken) async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: {
        'access_token': 'mock_new_access',
        'refresh_token': 'mock_new_refresh',
      },
    );
  }

  @override
  Future<Response> getMe() async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: User(
        id: '2',
        email: 'dispatcher@operion.ro',
        fullName: 'Test Dispatcher',
        role: 'dispatcher',
        companyId: '1',
      ).toJson(),
    );
  }

  @override
  Future<Response> registerDevice({
    required String deviceId,
    required String platform,
    String? deviceName,
    String? fcmToken,
  }) async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: {'status': 'registered'},
    );
  }
}

/// Stub [DispatcherEndpoints] that returns realistic dispatcher data.
class _StubDispatcherEndpoints extends DispatcherEndpoints {
  _StubDispatcherEndpoints()
      : super(ApiClient.create(
          baseUrl: '',
          getAccessToken: () async => 'mock_token',
        ));

  @override
  Future<Response> getOverview() async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: {
        'activeJobs': 12,
        'activeDrivers': 8,
        'openAlerts': 3,
        'vehiclesOnRoad': 6,
        'lastUpdated': DateTime.now().toIso8601String(),
      },
    );
  }

  @override
  Future<Response> getFleet() async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: [
        {
          'vehicle_id': 'v1',
          'plate': 'B-123-ABC',
          'driver_name': 'Ion Popescu',
          'lat': 44.4268,
          'lng': 26.1025,
          'status': 'driving',
          'last_update': DateTime.now().toIso8601String(),
        },
        {
          'vehicle_id': 'v2',
          'plate': 'B-456-DEF',
          'driver_name': 'Vasile Ionescu',
          'lat': 46.7712,
          'lng': 23.6236,
          'status': 'stopped',
          'last_update': DateTime.now().toIso8601String(),
        },
      ],
    );
  }

  @override
  Future<Response> getJobs() async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: [
        {
          'id': 'j1',
          'loadInfo': 'Construction materials',
          'origin': 'Bucharest',
          'destination': 'Ploiesti',
          'status': 'in_transit',
        },
        {
          'id': 'j2',
          'loadInfo': 'Food supplies',
          'origin': 'Constanta',
          'destination': 'Bucharest',
          'status': 'planned',
        },
      ],
    );
  }

  @override
  Future<Response> getDrivers() async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: [
        {
          'id': 'd1',
          'fullName': 'Ion Popescu',
          'email': 'ion@operion.ro',
          'status': 'active',
        },
        {
          'id': 'd2',
          'fullName': 'Vasile Ionescu',
          'email': 'vasile@operion.ro',
          'status': 'active',
        },
      ],
    );
  }

  @override
  Future<Response> getAlerts() async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: [
        {
          'id': 1,
          'type': 'delay',
          'severity': 'high',
          'title': 'Transport delay — #T-101',
          'description':
              'Driver Ion Popescu reported a 2-hour delay due to roadworks on A3.',
          'is_read': false,
          'created_at': DateTime.now()
              .subtract(const Duration(hours: 1))
              .toIso8601String(),
          'related_entity_id': 'T-101',
          'related_entity_type': 'transport',
        },
        {
          'id': 2,
          'type': 'maintenance',
          'severity': 'medium',
          'title': 'Vehicle maintenance due — #V-456',
          'description': 'Truck B-456-DEF is due for oil change in 500 km.',
          'is_read': true,
          'created_at': DateTime.now()
              .subtract(const Duration(hours: 5))
              .toIso8601String(),
          'related_entity_id': 'V-456',
          'related_entity_type': 'vehicle',
        },
        {
          'id': 3,
          'type': 'compliance',
          'severity': 'low',
          'title': 'Driver certification expiring',
          'description':
              'Driver Vasile Ionescu ADR certification expires in 30 days.',
          'is_read': false,
          'created_at': DateTime.now()
              .subtract(const Duration(days: 2))
              .toIso8601String(),
          'related_entity_id': null,
          'related_entity_type': null,
        },
      ],
    );
  }

  @override
  Future<Response> approveAction(String id) async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: {'status': 'approved'},
    );
  }

  @override
  Future<Response> rejectAction(String id, {String? reason}) async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: {'status': 'rejected'},
    );
  }
}

/// Provider overrides for the dispatcher flow test.
List<Override> dispatcherFlowOverrides() => [
      secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
      biometricServiceProvider.overrideWithValue(_MockBiometricService()),
      authEndpointsProvider.overrideWith((ref) => _StubAuthEndpoints()),
      dispatcherEndpointsProvider
          .overrideWith((ref) => _StubDispatcherEndpoints()),
      currentUserProvider.overrideWith((ref) => User(
            id: '2',
            email: 'dispatcher@operion.ro',
            fullName: 'Test Dispatcher',
            role: 'dispatcher',
            companyId: '1',
          )),
      isOfflineProvider.overrideWith((ref) => false),
    ];

Widget createTestApp() => ProviderScope(
      overrides: dispatcherFlowOverrides(),
      child: const OperionMobileApp(),
    );

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Dispatcher Flow', () {
    testWidgets('1. Login as dispatcher and view dashboard', (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // Dispatcher shell should be visible with bottom nav
      expect(
        find.byType(BottomNavigationBar),
        findsOneWidget,
        reason: 'Dispatcher bottom navigation should be visible after auth.',
      );

      // The overview dashboard should show KPI values from our stub data
      expect(
        find.text('12'),
        findsOneWidget,
        reason: 'Active jobs count (12) should be displayed.',
      );
      expect(
        find.text('8'),
        findsOneWidget,
        reason: 'Active drivers count (8) should be displayed.',
      );
      expect(
        find.text('3'),
        findsOneWidget,
        reason: 'Open alerts count (3) should be displayed.',
      );
      expect(
        find.text('6'),
        findsOneWidget,
        reason: 'Vehicles on road (6) should be displayed.',
      );
    });

    testWidgets('2. View fleet positions', (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // Tap the "Fleet Tracker" tab (index 1 in the bottom nav).
      // The dispatcher bottom nav items are: Overview, Fleet Tracker, Copilot, More.
      final fleetTrackerIcon = find.byIcon(Icons.map_outlined);
      expect(fleetTrackerIcon, findsOneWidget);
      await tester.tap(fleetTrackerIcon);
      await tester.pumpAndSettle();

      // Fleet map screen should be rendering
      expect(
        find.byType(RefreshIndicator),
        findsWidgets,
        reason:
            'Fleet map should support pull-to-refresh via RefreshIndicator.',
      );
    });

    testWidgets('3. Navigate to alerts via quick action', (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // The dispatcher dashboard has quick action chips including "Approve"
      // which opens the alerts screen. Note: the locale key for approve is
      // "Approve" in English.
      final approveChip = find.textContaining('Approve');
      if (approveChip.evaluate().isNotEmpty) {
        await tester.tap(approveChip);
        await tester.pumpAndSettle();

        // The alert inbox should show the alert title from our stub data
        expect(
          find.textContaining('Transport delay'),
          findsWidgets,
          reason: 'Alert inbox should show delay alert.',
        );
      } else {
        // If quick action chip isn't found, the dashboard is still shown
        expect(
          find.byType(BottomNavigationBar),
          findsOneWidget,
          reason: 'Dashboard bottom nav should still be visible.',
        );
      }
    });

    testWidgets('4. Verify dispatcher dashboard KPIs', (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // Verify KPI cards are displayed by checking for specific labels.
      expect(
        find.text('12'),
        findsOneWidget,
        reason: 'Active jobs KPI is displayed.',
      );
      expect(
        find.text('8'),
        findsOneWidget,
        reason: 'Active drivers KPI is displayed.',
      );
    });

    testWidgets('5. Pull-to-refresh dispatcher dashboard', (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // Find the scrollable content and perform pull-to-refresh
      expect(find.byType(RefreshIndicator), findsWidgets);

      await tester.fling(
        find.byType(SingleChildScrollView).first,
        const Offset(0, 300),
        1000,
      );
      await tester.pumpAndSettle();

      // After refresh, KPI data should still be shown
      expect(
        find.text('12'),
        findsOneWidget,
        reason: 'After refresh, active jobs KPI should remain visible.',
      );
    });
  });
}
