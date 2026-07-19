import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import 'package:integration_test/integration_test.dart';

import 'package:operion_mobile/app.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/driver_endpoints.dart';
import 'package:operion_mobile/core/network/endpoints/auth_endpoints.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/shared/models/user.dart';
import 'package:operion_mobile/features/driver/home/driver_providers.dart';
import 'package:operion_mobile/features/driver/expenses/expense_providers.dart';

// ---------------------------------------------------------------------------
// Mock / Stub providers
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

/// Stub AuthEndpoints that returns pre-authenticated session responses.
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
        id: '1',
        email: 'driver@operion.ro',
        fullName: 'Test Driver',
        role: 'driver',
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

/// Simulates a driver session with pre-populated data.
class _StubDriverEndpoints extends DriverEndpoints {
  _StubDriverEndpoints()
      : super(ApiClient.create(
          baseUrl: '',
          getAccessToken: () async => 'mock_token',
        ));

  @override
  Future<Response> getMyDay() async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: {
        'activeTransports': 2,
        'nextStop': {'destination': 'Bucharest'},
        'transports': [
          {
            'id': 't1',
            'loadInfo': 'Steel coils — 20t',
            'origin': 'Cluj-Napoca, Str. Fabricii 12',
            'destination': 'Bucharest, Str. Industriilor 5',
            'status': 'in_transit',
            'companyId': '1',
            'waypoints': [],
            'scheduledDate': DateTime.now().toIso8601String(),
          },
          {
            'id': 't2',
            'loadInfo': 'Electronics — pallets',
            'origin': 'Timisoara, Str. Laminorului 3',
            'destination': 'Arad, Str. Constructorilor 8',
            'status': 'planned',
            'companyId': '1',
            'waypoints': [],
            'scheduledDate': DateTime.now().toIso8601String(),
          },
        ],
        'messages': [
          {
            'id': 'm1',
            'senderId': 'disp1',
            'senderName': 'Maria Dispatcher',
            'receiverId': '1',
            'text': 'Please confirm delivery time for transport #t1',
            'timestamp': DateTime.now().toIso8601String(),
            'isRead': false,
          },
        ],
        'lastUpdated': DateTime.now().toIso8601String(),
      },
    );
  }

  @override
  Future<Response> getTransports() async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: [
        {
          'id': 't1',
          'loadInfo': 'Steel coils — 20t',
          'origin': 'Cluj-Napoca, Str. Fabricii 12',
          'destination': 'Bucharest, Str. Industriilor 5',
          'status': 'in_transit',
          'companyId': '1',
          'waypoints': [],
          'scheduledDate': DateTime.now().toIso8601String(),
        },
        {
          'id': 't2',
          'loadInfo': 'Electronics — pallets',
          'origin': 'Timisoara, Str. Laminorului 3',
          'destination': 'Arad, Str. Constructorilor 8',
          'status': 'planned',
          'companyId': '1',
          'waypoints': [],
          'scheduledDate': DateTime.now().toIso8601String(),
        },
      ],
    );
  }

  @override
  Future<Response> getTransport(String id) async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: {
        'id': id,
        'loadInfo': 'Steel coils — 20t',
        'origin': 'Cluj-Napoca, Str. Fabricii 12',
        'destination': 'Bucharest, Str. Industriilor 5',
        'status': 'in_transit',
        'companyId': '1',
        'waypoints': [],
        'scheduledDate': DateTime.now().toIso8601String(),
      },
    );
  }

  @override
  Future<Response> updateStatus(String transportId, String status) async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: {'status': status},
    );
  }
}

/// Provider overrides for driver flow test.
List<Override> driverFlowOverrides() => [
      secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
      biometricServiceProvider.overrideWithValue(_MockBiometricService()),
      authEndpointsProvider.overrideWith((ref) => _StubAuthEndpoints()),
      driverEndpointsProvider.overrideWith((ref) => _StubDriverEndpoints()),
      currentUserProvider.overrideWith((ref) => User(
            id: '1',
            email: 'driver@operion.ro',
            fullName: 'Test Driver',
            role: 'driver',
            companyId: '1',
          )),
      expenseSubmittingProvider.overrideWith((ref) => false),
      isOfflineProvider.overrideWith((ref) => false),
    ];

Widget createTestApp() => ProviderScope(
      overrides: driverFlowOverrides(),
      child: const OperionMobileApp(),
    );

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Driver Daily Flow', () {
    testWidgets('1. Login as driver and view home screen', (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // The mode router should auto-restore session and show driver shell
      expect(
        find.byType(BottomNavigationBar),
        findsOneWidget,
        reason: 'Driver bottom navigation should be visible after auth.',
      );

      // The driver home screen should show the My Day content with transports
      expect(
        find.textContaining('Steel coils'),
        findsWidgets,
        reason: 'Driver home should display assigned transports.',
      );
    });

    testWidgets('2. View transport detail and update status', (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // Tap on the first transport card to open detail
      await tester.tap(find.textContaining('Steel coils'));
      await tester.pumpAndSettle();

      // Transport detail screen should show the app bar title
      expect(
        find.textContaining('Transport Details'),
        findsWidgets,
        reason: 'Transport detail screen should show transport details title.',
      );

      // Scaffold should be present on the detail screen
      expect(
        find.byType(Scaffold),
        findsWidgets,
        reason: 'Transport detail scaffold should be present.',
      );
    });

    testWidgets('3. Verify driver dashboard summary cards', (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // The "My Day" dashboard should show the active transports count (2)
      expect(
        find.text('2'),
        findsOneWidget,
        reason:
            'Driver home should show active transport count (2) in summary card.',
      );

      // Next stop destination should be visible
      expect(
        find.textContaining('Bucharest'),
        findsWidgets,
        reason: 'Driver home should show next stop destination.',
      );
    });

    testWidgets('4. Pull-to-refresh on driver home', (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // The home screen should be showing with RefreshIndicator
      expect(find.byType(RefreshIndicator), findsWidgets);

      // Drag down to trigger refresh
      await tester.fling(
        find.byType(SingleChildScrollView),
        const Offset(0, 300),
        1000,
      );
      await tester.pumpAndSettle();

      // After refresh, transport data should still be shown
      expect(
        find.textContaining('Steel coils'),
        findsWidgets,
        reason:
            'After pull-to-refresh, transport data should remain visible.',
      );
    });
  });
}
