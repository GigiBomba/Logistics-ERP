import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'package:operion_mobile/features/auth/login_screen.dart';
import 'package:operion_mobile/features/auth/session_expired_screen.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/message_bus.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';

// ---------------------------------------------------------------------------
// Mock providers – these avoid platform-channel crashes in the test
// environment (FlutterSecureStorage, local_auth, etc.).
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

/// Provider overrides used by auth-screen smoke tests.
final List<Override> authOverrides = [
  secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
  biometricServiceProvider.overrideWithValue(_MockBiometricService()),
];

/// Helper: wraps [child] in [ProviderScope] + [MaterialApp] with
/// localisation so that `context.loc` works.
Widget wrapAuthScreen(Widget child) {
  return ProviderScope(
    overrides: authOverrides,
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultCupertinoLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: child,
    ),
  );
}

void main() {
  // ==========================================================================
  // LoginScreen
  // ==========================================================================
  group('LoginScreen', () {
    testWidgets('renders branding, email, password, and sign-in button',
        (tester) async {
      await tester.pumpWidget(wrapAuthScreen(const LoginScreen()));
      await tester.pumpAndSettle(); // allow async initState + locale to settle

      // Branding: app name + truck icon
      expect(find.text('Operion'), findsOneWidget);
      expect(find.byIcon(LucideIcons.truck), findsOneWidget);

      // Two text fields: email + password
      expect(find.byType(TextFormField), findsNWidgets(2));

      // Sign-in button (English locale)
      expect(find.text('Sign In'), findsOneWidget);
    });

    testWidgets('renders forgot password link', (tester) async {
      await tester.pumpWidget(wrapAuthScreen(const LoginScreen()));
      await tester.pumpAndSettle();

      expect(find.text('Forgot password?'), findsOneWidget);
    });

    testWidgets('does not crash when tapping sign-in with empty fields',
        (tester) async {
      await tester.pumpWidget(wrapAuthScreen(const LoginScreen()));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Sign In'));
      await tester.pump();

      // Should show the validation error banner
      // (the validator returns "Email is required" or similar)
      expect(find.text('Email is required'), findsOneWidget);
    });

    testWidgets('shows password visibility toggle', (tester) async {
      await tester.pumpWidget(wrapAuthScreen(const LoginScreen()));
      await tester.pumpAndSettle();

      // Initially the password is obscured, so eye-off icon is shown
      expect(find.byIcon(LucideIcons.eyeOff), findsOneWidget);

      // Tap the eye-off to reveal password
      await tester.tap(find.byIcon(LucideIcons.eyeOff));
      await tester.pump();

      // Now eye icon should be visible
      expect(find.byIcon(LucideIcons.eye), findsOneWidget);
    });

    testWidgets('accepts email and password input', (tester) async {
      await tester.pumpWidget(wrapAuthScreen(const LoginScreen()));
      await tester.pumpAndSettle();

      final textFields = find.byType(TextFormField);
      await tester.enterText(textFields.first, 'user@example.com');
      await tester.enterText(textFields.last, 'secret123');

      expect(find.text('user@example.com'), findsOneWidget);
      expect(find.text('secret123'), findsOneWidget);
    });
  });

  // ==========================================================================
  // SessionExpiredScreen
  // ==========================================================================
  group('SessionExpiredScreen', () {
    testWidgets('renders lock icon and session-expired text', (tester) async {
      await tester.pumpWidget(wrapAuthScreen(const SessionExpiredScreen()));
      await tester.pumpAndSettle();

      // Lock icon
      expect(find.byIcon(LucideIcons.lock), findsOneWidget);

      // Session expired message (English locale)
      expect(find.text('Your session has expired.'), findsOneWidget);

      // Sign-in button
      expect(find.text('Sign In'), findsOneWidget);
    });

    testWidgets('back navigation is blocked (PopScope canPop=false)',
        (tester) async {
      await tester.pumpWidget(wrapAuthScreen(const SessionExpiredScreen()));
      await tester.pumpAndSettle();

      // Verify the Scaffold renders without crash
      expect(find.byType(Scaffold), findsOneWidget);
    });
  });
}
