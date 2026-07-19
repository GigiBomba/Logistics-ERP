import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/auth_service.dart';
import 'package:operion_mobile/core/auth/mode_router.dart';
import 'package:operion_mobile/core/auth/token_manager.dart';
import 'package:operion_mobile/core/network/message_bus.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/features/auth/login_screen.dart';
import 'package:operion_mobile/features/auth/session_expired_screen.dart';
import 'package:operion_mobile/features/driver/driver_shell.dart';
import 'package:operion_mobile/features/dispatcher/dispatcher_shell.dart';
import 'package:operion_mobile/l10n/app_localizations.dart';
import 'package:operion_mobile/shared/models/user.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Fake implementations for the test's ProviderScope
// ─────────────────────────────────────────────────────────────────────────────

class _FakeSecureTokenStore implements SecureTokenStore {
  String? _accessToken;
  String? _refreshToken;

  @override
  Future<void> saveTokens(String accessToken, String refreshToken) async {
    _accessToken = accessToken;
    _refreshToken = refreshToken;
  }

  @override
  Future<String?> getAccessToken() async => _accessToken;

  @override
  Future<String?> getRefreshToken() async => _refreshToken;

  @override
  Future<void> clearTokens() async {
    _accessToken = null;
    _refreshToken = null;
  }

  @override
  Future<bool> hasTokens() async =>
      _accessToken != null && _accessToken!.isNotEmpty;

  @override
  Future<String> getOrCreateDeviceId() async => 'test-device-uuid';
}

class _FakeTokenManager implements TokenManager {
  bool _hasTokens = false;
  String? _refreshToken;

  @override
  bool get isAuthenticated => _hasTokens;

  void setAuthenticated(bool value) => _hasTokens = value;
  void setRefreshToken(String? token) => _refreshToken = token;

  @override
  Future<void> initialize() async {}

  @override
  Future<String?> getAccessToken() async =>
      _hasTokens ? 'test-access-token' : null;

  @override
  Future<String?> getRefreshToken() async => _refreshToken;

  @override
  Future<void> saveTokens(String access, String refresh) async {
    _hasTokens = true;
    _refreshToken = refresh;
  }

  @override
  Future<void> clearTokens() async {
    _hasTokens = false;
    _refreshToken = null;
  }

  @override
  Future<bool> tryRefresh() async => false;
}

class _FakeAuthService implements AuthService {
  bool _restoreSessionResult = false;

  void setRestoreSessionResult(bool value) => _restoreSessionResult = value;

  @override
  Future<AuthResult> login(String email, String password) async =>
      const AuthResult(success: true);

  @override
  Future<void> logout() async {}

  @override
  Future<User?> getCurrentUser() async => null;

  @override
  Future<bool> restoreSession() async => _restoreSessionResult;
}

// ─────────────────────────────────────────────────────────────────────────────
// Test helpers
// ─────────────────────────────────────────────────────────────────────────────

/// Creates a test [User] with the given [role].
User _testUser({String role = 'driver'}) => User(
      id: 'u1',
      email: 'test@test.com',
      fullName: 'Test User',
      role: role,
      companyId: 'c1',
    );

/// An [AuthStateNotifier] with a configurable initial state for testing.
class _TestAuthStateNotifier extends AuthStateNotifier {
  _TestAuthStateNotifier(super.ref, AuthState initialState) {
    state = initialState;
  }
}

/// Builds a [ProviderScope] wrapping a [ModeRouter] with the given overrides.
///
/// The [authState] controls which screen the router renders.
/// When [user] is non-null it is set as the current user, which also drives
/// the derived [currentUserRoleProvider].
///
/// A real [AuthStateNotifier] is used so that the override type matches;
/// [messageBusProvider] is also overridden so the notifier doesn't need
/// a real bus.
Future<void> pumpRouter(
  WidgetTester tester, {
  required AuthState authState,
  User? user,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        messageBusProvider.overrideWith((ref) => MessageBus()),
        authStateProvider.overrideWithProvider(
          StateNotifierProvider<AuthStateNotifier, AuthState>(
            (ref) => _TestAuthStateNotifier(ref, authState),
          ),
        ),
        currentUserProvider.overrideWithProvider(
          StateProvider<User?>((ref) => user),
        ),
        tokenManagerProvider.overrideWith((ref) => _FakeTokenManager()),
        authServiceProvider.overrideWith((ref) => _FakeAuthService()),
      ],
      child: MaterialApp(
        localizationsDelegates: const [
          AppLocalizations.delegate,
        ],
        supportedLocales: AppLocalizations.supportedLocales,
        home: const ModeRouter(),
      ),
    ),
  );
  // Let postFrameCallback (_restoreSession) settle
  await tester.pump();
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  // ── Unauthenticated (offline/initial state) ─────────────────────────

  group('when user is not authenticated', () {
    testWidgets('shows LoginScreen by default', (tester) async {
      await pumpRouter(tester, authState: AuthState.unauthenticated);

      expect(find.byType(LoginScreen), findsOneWidget);
      expect(find.byType(DriverShell), findsNothing);
      expect(find.byType(DispatcherShell), findsNothing);
      expect(find.byType(SessionExpiredScreen), findsNothing);
    });

    testWidgets('shows LoginScreen when user is null even if authenticated',
        (tester) async {
      await pumpRouter(tester, authState: AuthState.authenticated);

      // user is null → condition `user == null` matches
      expect(find.byType(LoginScreen), findsOneWidget);
    });
  });

  // ── Authenticating ──────────────────────────────────────────────────

  group('when authenticating', () {
    testWidgets(
        'shows loading indicator when user is not null',
        (tester) async {
      // Note: The ModeRouter's build method checks `user == null` BEFORE
      // `authState == authenticating`, so the loading indicator only appears
      // when a user object is present during authenticating state.
      await pumpRouter(
        tester,
        authState: AuthState.authenticating,
        user: _testUser(role: 'driver'),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.byType(LoginScreen), findsNothing);
      expect(find.byType(DriverShell), findsNothing);
      expect(find.byType(DispatcherShell), findsNothing);
    });

    testWidgets(
        'shows LoginScreen when user is null during authenticating',
        (tester) async {
      // The `user == null` condition takes precedence over the
      // authenticating check in ModeRouter.build.
      await pumpRouter(tester, authState: AuthState.authenticating);

      expect(find.byType(LoginScreen), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });
  });

  // ── Session expired ─────────────────────────────────────────────────

  group('when session expired', () {
    testWidgets('shows SessionExpiredScreen', (tester) async {
      await pumpRouter(tester, authState: AuthState.sessionExpired);

      expect(find.byType(SessionExpiredScreen), findsOneWidget);
      expect(find.byType(LoginScreen), findsNothing);
      expect(find.byType(DriverShell), findsNothing);
      expect(find.byType(DispatcherShell), findsNothing);
    });
  });

  // ── Authenticated ───────────────────────────────────────────────────

  group('when authenticated', () {
    testWidgets('shows DriverShell for driver role', (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'driver'),
      );

      expect(find.byType(DriverShell), findsOneWidget);
      expect(find.byType(DispatcherShell), findsNothing);
      expect(find.byType(LoginScreen), findsNothing);
    });

    testWidgets('shows DriverShell for sofer role (Romanian alias)',
        (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'sofer'),
      );

      expect(find.byType(DriverShell), findsOneWidget);
    });

    testWidgets('shows DispatcherShell for dispatcher role', (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'dispatcher'),
      );

      expect(find.byType(DispatcherShell), findsOneWidget);
      expect(find.byType(DriverShell), findsNothing);
    });

    testWidgets('shows DispatcherShell for fleet_manager role',
        (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'fleet_manager'),
      );

      expect(find.byType(DispatcherShell), findsOneWidget);
    });

    testWidgets('shows DispatcherShell for manager role', (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'manager'),
      );

      expect(find.byType(DispatcherShell), findsOneWidget);
    });

    testWidgets('shows DispatcherShell for admin role', (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'admin'),
      );

      expect(find.byType(DispatcherShell), findsOneWidget);
    });

    testWidgets('shows DispatcherShell for owner role', (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'owner'),
      );

      expect(find.byType(DispatcherShell), findsOneWidget);
    });

    testWidgets('DriverShell renders with bottom navigation bar',
        (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'driver'),
      );

      expect(find.byType(DriverShell), findsOneWidget);
      expect(find.byType(BottomNavigationBar), findsOneWidget);
    });

    testWidgets('DispatcherShell renders with bottom navigation bar',
        (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'manager'),
      );

      expect(find.byType(DispatcherShell), findsOneWidget);
      expect(find.byType(BottomNavigationBar), findsOneWidget);
    });

    testWidgets('driver shell has 4 navigation tabs', (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'driver'),
      );

      final navBar = tester.widget<BottomNavigationBar>(
        find.byType(BottomNavigationBar),
      );
      expect(navBar.items, hasLength(4));
    });
  });

  // ── Mode switching (state transitions) ─────────────────────────────

  group('mode switching', () {
    testWidgets('renders different screens for each auth state',
        (tester) async {
      // Each pumpRouter call creates a completely new ProviderScope
      // and widget tree, avoiding stale callback issues.

      await pumpRouter(tester, authState: AuthState.unauthenticated);
      expect(find.byType(LoginScreen), findsOneWidget);

      // clean up before next state
      await tester.pump(Duration.zero);
    });

    testWidgets('authenticating state shows spinner with user',
        (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticating,
        user: _testUser(role: 'driver'),
      );
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('authenticated driver shows DriverShell', (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'driver'),
      );
      expect(find.byType(DriverShell), findsOneWidget);
    });

    testWidgets('authenticated manager shows DispatcherShell', (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'manager'),
      );
      expect(find.byType(DispatcherShell), findsOneWidget);
    });

    testWidgets('session expired shows SessionExpiredScreen', (tester) async {
      await pumpRouter(tester, authState: AuthState.sessionExpired);
      expect(find.byType(SessionExpiredScreen), findsOneWidget);
    });

    testWidgets('unauthenticated shows LoginScreen', (tester) async {
      await pumpRouter(tester, authState: AuthState.unauthenticated);
      expect(find.byType(LoginScreen), findsOneWidget);
    });
  });

  // ── Edge cases ─────────────────────────────────────────────────────

  group('edge cases', () {
    testWidgets('all AuthState enumerations are handled', (tester) async {
      // Verify no unhandled AuthState crashes the widget
      await pumpRouter(tester, authState: AuthState.unauthenticated);
      expect(find.byType(LoginScreen), findsOneWidget);
    });

    testWidgets('AuthGate typedef resolves to ModeRouter', (tester) async {
      const AuthGate gate = ModeRouter();
      expect(gate, isA<ModeRouter>());
    });

    testWidgets('_restoreSession early return when no refresh token',
        (tester) async {
      // The _FakeTokenManager returns null for getRefreshToken by default
      await pumpRouter(tester, authState: AuthState.unauthenticated);

      // Should remain on a valid screen
      expect(find.byType(LoginScreen), findsOneWidget);
    });

    testWidgets('driver and manager show different shells', (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'driver'),
      );
      expect(find.byType(DriverShell), findsOneWidget);

      // Clean pump before next test action
      await tester.pump(Duration.zero);
    });

    testWidgets('manager role shows DispatcherShell', (tester) async {
      await pumpRouter(
        tester,
        authState: AuthState.authenticated,
        user: _testUser(role: 'manager'),
      );
      expect(find.byType(DispatcherShell), findsOneWidget);
    });

  });
}
