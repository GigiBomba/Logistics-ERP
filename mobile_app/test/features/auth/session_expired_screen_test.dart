import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/features/auth/session_expired_screen.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';

// ── Mock BiometricService (avoids platform-channel crash) ──────────────────

class _MockBiometricService extends BiometricService {
  bool _available = false;
  bool _authenticateResult = false;

  void setAvailable(bool value) => _available = value;
  void setAuthenticateResult(bool value) => _authenticateResult = value;

  @override
  Future<bool> isAvailable() async => _available;

  @override
  Future<bool> authenticate({required String reason}) async =>
      _authenticateResult;
}

final _mockBiometricService = _MockBiometricService();

/// Provider overrides: only biometrics mocked — authService is left
/// un-mocked because the Sign In button triggers deep provider chains
/// that require `--dart-define=OPERION_API_KEY`. Tests that tap Sign In
/// are tested at the rendering level only.
final List<Override> _sessionOverrides = [
  biometricServiceProvider.overrideWithValue(_mockBiometricService),
];

/// Helper: wraps [child] in [ProviderScope] + [MaterialApp] with
/// localisation so that `context.loc` works.
Widget wrapSessionExpiredScreen() {
  return ProviderScope(
    overrides: _sessionOverrides,
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const SessionExpiredScreen(),
    ),
  );
}

void main() {
  // ==========================================================================
  // Initial state — expiry message
  // ==========================================================================
  group('SessionExpiredScreen — initial state', () {
    testWidgets('renders lock icon', (tester) async {
      await tester.pumpWidget(wrapSessionExpiredScreen());
      await tester.pumpAndSettle();

      expect(find.byIcon(LucideIcons.lock), findsOneWidget);
    });

    testWidgets('renders session expired message', (tester) async {
      await tester.pumpWidget(wrapSessionExpiredScreen());
      await tester.pumpAndSettle();

      expect(find.text('Your session has expired.'), findsOneWidget);
    });

    testWidgets('renders Sign In button for relogin', (tester) async {
      await tester.pumpWidget(wrapSessionExpiredScreen());
      await tester.pumpAndSettle();

      expect(find.text('Sign In'), findsOneWidget);
    });

    testWidgets('does not show biometric section when unavailable',
        (tester) async {
      _mockBiometricService.setAvailable(false);
      await tester.pumpWidget(wrapSessionExpiredScreen());
      await tester.pumpAndSettle();

      expect(find.byIcon(LucideIcons.fingerprint), findsNothing);
    });
  });

  // ==========================================================================
  // Back navigation blocked
  // ==========================================================================
  group('SessionExpiredScreen — navigation block', () {
    testWidgets('back navigation is blocked (PopScope canPop=false)',
        (tester) async {
      await tester.pumpWidget(wrapSessionExpiredScreen());
      await tester.pumpAndSettle();

      // Verify PopScope exists with canPop = false
      final popScope = tester.widget<PopScope>(find.byType(PopScope));
      expect(popScope.canPop, false);
    });

    testWidgets('Scaffold renders without crash', (tester) async {
      await tester.pumpWidget(wrapSessionExpiredScreen());
      await tester.pumpAndSettle();

      expect(find.byType(Scaffold), findsOneWidget);
    });
  });

  // ==========================================================================
  // Relogin action — rendering verification only
  // ==========================================================================
  group('SessionExpiredScreen — relogin action', () {
    testWidgets('Sign In button is rendered', (tester) async {
      await tester.pumpWidget(wrapSessionExpiredScreen());
      await tester.pumpAndSettle();

      // Verify the button exists and has the correct label
      // (actual tap requires mocking authServiceProvider which depends on
      // platform channels not available in test env without dart-define)
      expect(find.text('Sign In'), findsOneWidget);
    });
  });

  // ==========================================================================
  // Biometric unlock (when available)
  // ==========================================================================
  group('SessionExpiredScreen — biometric unlock', () {
    setUp(() {
      _mockBiometricService.setAvailable(true);
    });

    testWidgets('shows biometric section when available', (tester) async {
      await tester.pumpWidget(wrapSessionExpiredScreen());
      await tester.pumpAndSettle();

      expect(find.byIcon(LucideIcons.fingerprint), findsOneWidget);
      expect(
        find.text(
            'Authenticate using fingerprint or face recognition'),
        findsOneWidget,
      );
    });

    testWidgets('tapping biometric icon runs authentication',
        (tester) async {
      _mockBiometricService.setAuthenticateResult(false);
      await tester.pumpWidget(wrapSessionExpiredScreen());
      await tester.pumpAndSettle();

      // Tap fingerprint icon — uses biometricServiceProvider which is mocked
      await tester.tap(find.byIcon(LucideIcons.fingerprint));
      await tester.pumpAndSettle();

      // Screen should still be visible after failed auth
      expect(find.byType(SessionExpiredScreen), findsOneWidget);
    });
  });
}
