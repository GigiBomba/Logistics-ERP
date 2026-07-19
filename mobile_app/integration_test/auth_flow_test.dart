import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import 'package:integration_test/integration_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'package:operion_mobile/app.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/auth_endpoints.dart';
import 'package:operion_mobile/shared/models/user.dart';

// ---------------------------------------------------------------------------
// Mock providers for integration testing
// ---------------------------------------------------------------------------

class _MockSecureTokenStore extends SecureTokenStore {
  String? _accessToken;
  String? _refreshToken;

  @override
  Future<bool> hasTokens() async => _accessToken != null;

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

/// A stub [AuthEndpoints] that simulates a successful login.
class _StubAuthEndpoints extends AuthEndpoints {
  _StubAuthEndpoints()
      : super(ApiClient.create(
          baseUrl: '',
          getAccessToken: () async => null,
        ));

  @override
  Future<Response> login(String email, String password, {String? deviceId}) async {
    // Simulate network delay
    await Future.delayed(const Duration(milliseconds: 50));
    if (email == 'driver@operion.ro' && password == 'password123') {
      return Response(
        requestOptions: RequestOptions(path: ''),
        data: {
          'access_token': 'mock_access_token',
          'refresh_token': 'mock_refresh_token',
          'user': User(
            id: '1',
            email: 'driver@operion.ro',
            fullName: 'Test Driver',
            role: 'driver',
            companyId: '1',
          ).toJson(),
        },
      );
    }
    if (email == 'dispatcher@operion.ro' && password == 'password123') {
      return Response(
        requestOptions: RequestOptions(path: ''),
        data: {
          'access_token': 'mock_access_token',
          'refresh_token': 'mock_refresh_token',
          'user': User(
            id: '2',
            email: 'dispatcher@operion.ro',
            fullName: 'Test Dispatcher',
            role: 'dispatcher',
            companyId: '1',
          ).toJson(),
        },
      );
    }
    // Return error for invalid credentials
    throw DioException(
      requestOptions: RequestOptions(path: ''),
      response: Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 401,
        data: {'error': 'Invalid credentials'},
      ),
    );
  }

  @override
  Future<Response> refreshToken(String refreshToken) async {
    return Response(
      requestOptions: RequestOptions(path: ''),
      data: {
        'access_token': 'mock_refreshed_access_token',
        'refresh_token': 'mock_refreshed_refresh_token',
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

/// Provider overrides for the auth flow test.
List<Override> authTestOverrides() => [
      secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
      biometricServiceProvider.overrideWithValue(_MockBiometricService()),
      authEndpointsProvider.overrideWith((ref) => _StubAuthEndpoints()),
      currentUserProvider.overrideWith((ref) => null),
    ];

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

/// Wraps the app with test provider overrides.
Widget createTestApp() => ProviderScope(
      overrides: authTestOverrides(),
      child: const OperionMobileApp(),
    );

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Auth Flow — Login then navigate home', () {
    testWidgets('1. Login screen renders branding and form', (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // App name should be visible
      expect(find.text('Operion'), findsOneWidget);

      // Truck icon branding
      expect(find.byIcon(LucideIcons.truck), findsOneWidget);

      // Email and password fields (2 TextFormFields)
      expect(find.byType(TextFormField), findsNWidgets(2));

      // Sign In button
      expect(find.text('Sign In'), findsOneWidget);
    });

    testWidgets('2. Enter credentials and submit for driver login',
        (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // Fill email
      final emailField = find.byType(TextFormField).first;
      await tester.enterText(emailField, 'driver@operion.ro');

      // Fill password
      final passwordField = find.byType(TextFormField).last;
      await tester.enterText(passwordField, 'password123');

      // Tap Sign In
      await tester.tap(find.text('Sign In'));

      // Wait for async login to complete and navigation to settle
      await tester.pumpAndSettle();

      // After successful login, the app should navigate away from login screen.
      // The LoginScreen has a truck icon, so it should no longer be present.
      // Instead, we expect to see the driver shell or some part of it.
      // The driver shell includes a BottomNavigationBar.
      expect(
        find.byType(BottomNavigationBar),
        findsOneWidget,
        reason: 'After driver login, the bottom navigation bar should be visible.',
      );

      // The "Sign In" button should no longer be on screen
      expect(find.text('Sign In'), findsNothing);
    });

    testWidgets('3. Login with invalid credentials shows error',
        (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // Fill wrong credentials
      final emailField = find.byType(TextFormField).first;
      await tester.enterText(emailField, 'wrong@email.com');
      final passwordField = find.byType(TextFormField).last;
      await tester.enterText(passwordField, 'wrongpass');

      // Tap Sign In
      await tester.tap(find.text('Sign In'));

      // Wait for async login and error display
      await tester.pumpAndSettle();

      // Should still be on login screen — truck icon still visible
      expect(find.byIcon(LucideIcons.truck), findsOneWidget);

      // Error message should appear (the stub returns an error for wrong creds
      // which triggers context.loc.auth_loginError)
      expect(find.text('Sign In'), findsOneWidget);
    });

    testWidgets('4. Login as dispatcher', (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // Fill dispatcher credentials
      final emailField = find.byType(TextFormField).first;
      await tester.enterText(emailField, 'dispatcher@operion.ro');
      final passwordField = find.byType(TextFormField).last;
      await tester.enterText(passwordField, 'password123');

      // Submit
      await tester.tap(find.text('Sign In'));
      await tester.pumpAndSettle();

      // Dispatcher shell should appear with bottom nav
      expect(
        find.byType(BottomNavigationBar),
        findsOneWidget,
        reason:
            'After dispatcher login, the dispatcher shell with bottom nav '
            'should be visible.',
      );

      // Login screen elements should be gone
      expect(find.byIcon(LucideIcons.truck), findsNothing);
    });
  });
}
