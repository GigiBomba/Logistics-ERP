import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/message_bus.dart';
import 'package:operion_mobile/features/auth/login_screen.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';

// ── Mock dependencies ──────────────────────────────────────────────────────

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

/// Provider overrides for login screen tests.
final List<Override> _loginOverrides = [
  secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
  biometricServiceProvider.overrideWithValue(_MockBiometricService()),
];

/// Helper: wraps [child] in [ProviderScope] + [MaterialApp] with
/// localisation so that `context.loc` works.
Widget wrapLoginScreen() {
  return ProviderScope(
    overrides: _loginOverrides,
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const LoginScreen(),
    ),
  );
}

void main() {
  // ==========================================================================
  // Initial state — branding & form rendering
  // ==========================================================================
  group('LoginScreen — initial state', () {
    testWidgets('renders app branding with truck icon and name',
        (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      expect(find.byIcon(LucideIcons.truck), findsOneWidget);
      expect(find.text('Operion'), findsOneWidget);
    });

    testWidgets('renders email and password text fields', (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      expect(find.byType(TextFormField), findsNWidgets(2));
    });

    testWidgets('shows Email and Password labels', (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      expect(find.text('Email'), findsOneWidget);
      expect(find.text('Password'), findsOneWidget);
    });

    testWidgets('renders Sign In button', (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      expect(find.text('Sign In'), findsOneWidget);
    });

    testWidgets('renders forgot password link', (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      expect(find.text('Forgot password?'), findsOneWidget);
    });
  });

  // ==========================================================================
  // Form validation
  // ==========================================================================
  group('LoginScreen — form validation', () {
    testWidgets('shows email required error on empty submit', (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Sign In'));
      await tester.pump();

      expect(find.text('Email is required'), findsOneWidget);
    });

    testWidgets('shows email validation error for invalid email',
        (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      final fields = find.byType(TextFormField);
      await tester.enterText(fields.first, 'not-an-email');
      await tester.pumpAndSettle();

      await tester.tap(find.text('Sign In'));
      await tester.pump();

      expect(find.text('Enter a valid email'), findsOneWidget);
    });

    testWidgets('shows password required error when email valid but password empty',
        (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      final fields = find.byType(TextFormField);
      await tester.enterText(fields.first, 'user@example.com');
      await tester.pumpAndSettle();

      await tester.tap(find.text('Sign In'));
      await tester.pump();

      expect(find.text('Password is required'), findsOneWidget);
    });

    testWidgets('passes validation with valid email and non-empty password',
        (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      final fields = find.byType(TextFormField);
      await tester.enterText(fields.first, 'user@example.com');
      await tester.enterText(fields.last, 'mypassword');
      await tester.pumpAndSettle();

      // No validation errors should appear
      expect(find.text('Email is required'), findsNothing);
      expect(find.text('Enter a valid email'), findsNothing);
      expect(find.text('Password is required'), findsNothing);
    });
  });

  // ==========================================================================
  // Password visibility toggle
  // ==========================================================================
  group('LoginScreen — password visibility', () {
    testWidgets('password is obscured by default showing eye-off icon',
        (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      expect(find.byIcon(LucideIcons.eyeOff), findsOneWidget);
    });

    testWidgets('tapping eye-off reveals password and shows eye icon',
        (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(LucideIcons.eyeOff));
      await tester.pump();

      expect(find.byIcon(LucideIcons.eye), findsOneWidget);
    });

    testWidgets('tapping eye re-obscures password and shows eye-off icon',
        (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      // Reveal
      await tester.tap(find.byIcon(LucideIcons.eyeOff));
      await tester.pump();

      // Hide again
      await tester.tap(find.byIcon(LucideIcons.eye));
      await tester.pump();

      expect(find.byIcon(LucideIcons.eyeOff), findsOneWidget);
    });
  });

  // ==========================================================================
  // Input handling
  // ==========================================================================
  group('LoginScreen — input handling', () {
    testWidgets('accepts email input', (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      final fields = find.byType(TextFormField);
      await tester.enterText(fields.first, 'driver@operion.ro');
      await tester.pumpAndSettle();

      expect(find.text('driver@operion.ro'), findsOneWidget);
    });

    testWidgets('accepts password input', (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      final fields = find.byType(TextFormField);
      await tester.enterText(fields.last, 'securePass123');
      await tester.pumpAndSettle();

      // Password text is hidden but the controller holds the value
      final passwordField = tester.widget<TextFormField>(fields.last);
      expect(passwordField.controller?.text, 'securePass123');
    });
  });

  // ==========================================================================
  // Screen layout
  // ==========================================================================
  group('LoginScreen — layout', () {
    testWidgets('form is centered in a scroll view', (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      expect(find.byType(SingleChildScrollView), findsOneWidget);
      expect(find.byType(Card), findsOneWidget);
    });

    testWidgets('does not show biometric section by default', (tester) async {
      await tester.pumpWidget(wrapLoginScreen());
      await tester.pumpAndSettle();

      // Biometric section only shows when biometricAvailable is true
      expect(find.byIcon(LucideIcons.fingerprint), findsNothing);
    });
  });
}
