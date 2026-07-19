// ---------------------------------------------------------------------------
// settings_screen_test.dart — Settings screen widget tests
//
// Covers: screen rendering, language selection, theme toggle, logout flow,
// section headers, app version display.
// ---------------------------------------------------------------------------

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/auth_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/message_bus.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/settings/settings_screen.dart';
import 'package:operion_mobile/shared/models/user.dart';

// ---------------------------------------------------------------------------
// Mock dependencies
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

  @override
  Future<String> getOrCreateDeviceId() async => 'test-device-id';
}

/// Minimal [AuthService] stub that tracks logout calls.
class _MockAuthService implements AuthService {
  bool logoutCalled = false;

  @override
  Future<void> logout() async {
    logoutCalled = true;
  }

  @override
  Future<AuthResult> login(String email, String password) async {
    return const AuthResult(success: false);
  }

  @override
  Future<User?> getCurrentUser() async => null;

  @override
  Future<bool> restoreSession() async => false;
}

class _MockMessageBus extends MessageBus {
  @override
  Stream<BusEvent> get stream => const Stream.empty();
}

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

/// Common provider overrides used by all tests in this suite.
List<Override> _baseOverrides({
  Locale initialLocale = const Locale('en'),
  ThemeMode initialThemeMode = ThemeMode.system,
}) => [
  secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
  localeProvider.overrideWith((ref) => initialLocale),
  themeModeProvider.overrideWith((ref) => initialThemeMode),
  currentUserProvider.overrideWith((ref) => null),
  authStateProvider.overrideWith((ref) => AuthStateNotifier(ref)),
  messageBusProvider.overrideWithValue(_MockMessageBus()),
];

/// Wraps [child] in a ProviderScope + MaterialApp with English locale so
/// `context.loc` resolves deterministically.
Widget _wrap(Widget child, {List<Override>? extraOverrides}) {
  return ProviderScope(
    overrides: [
      ..._baseOverrides(),
      if (extraOverrides != null) ...extraOverrides,
    ],
    child: MaterialApp(
      locale: const Locale('en'),
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: child,
    ),
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  group('SettingsScreen', () {
    testWidgets('1. renders AppBar with Settings title', (tester) async {
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      expect(find.text('Settings'), findsOneWidget);
    });

    testWidgets('2. renders language section header', (tester) async {
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      expect(find.text('LANGUAGE'), findsOneWidget);
    });

    testWidgets('3. renders theme section header', (tester) async {
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      expect(find.text('THEME'), findsOneWidget);
    });

    testWidgets('4. renders app version section header', (tester) async {
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      expect(find.text('APP VERSION'), findsOneWidget);
    });

    testWidgets('5. shows version number 1.0.0+1', (tester) async {
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      expect(find.text('1.0.0+1'), findsOneWidget);
    });

    testWidgets('6. renders logout button with text', (tester) async {
      // Use a taller surface so off-screen widgets are visible
      await tester.binding.setSurfaceSize(const Size(800, 1200));
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      // Button text via locale (skipOffstage: false to find off-screen widgets)
      expect(find.text('Sign Out', skipOffstage: false), findsOneWidget);
    });

    testWidgets('7. renders language radio options', (tester) async {
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      // "Română" appears twice: once as title (loc.settings_languageRo)
      // and once as subtitle (hardcoded 'Română')
      expect(find.text('Română'), findsAtLeast(1));
      // "English" appears twice for the same reason
      expect(find.text('English'), findsAtLeast(1));
    });

    testWidgets('8. renders theme radio options', (tester) async {
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      // "Light" appears as System subtitle AND as Light radio title
      expect(find.text('System'), findsOneWidget);
      expect(find.text('Light'), findsAtLeast(1));
      expect(find.text('Dark'), findsOneWidget);
    });

    testWidgets('9. tapping English radio selects English locale',
        (tester) async {
      // Start with Romanian so we can see the switch
      await tester.pumpWidget(_wrap(
        const SettingsScreen(),
        extraOverrides: [
          localeProvider.overrideWith((ref) => const Locale('ro')),
        ],
      ));
      await tester.pumpAndSettle();

      // Find the English RadioListTile by its value
      final englishListTile = find.descendant(
        of: find.byType(RadioListTile<Locale>),
        matching: find.text('English'),
      );
      await tester.tap(englishListTile.first);
      await tester.pump();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SettingsScreen)),
      );
      expect(container.read(localeProvider), const Locale('en'));
    });

    testWidgets('10. tapping Română radio selects Romanian locale',
        (tester) async {
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      // Find the Română RadioListTile by its value
      final romanianListTile = find.descendant(
        of: find.byType(RadioListTile<Locale>),
        matching: find.text('Română'),
      );
      await tester.tap(romanianListTile.first);
      await tester.pump();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SettingsScreen)),
      );
      expect(container.read(localeProvider), const Locale('ro'));
    });

    testWidgets('11. tapping System theme radio sets ThemeMode.system',
        (tester) async {
      await tester.pumpWidget(_wrap(
        const SettingsScreen(),
        extraOverrides: [
          themeModeProvider.overrideWith((ref) => ThemeMode.light),
        ],
      ));
      await tester.pumpAndSettle();

      // Tap the System radio
      await tester.tap(find.text('System'));
      await tester.pump();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SettingsScreen)),
      );
      expect(container.read(themeModeProvider), ThemeMode.system);
    });

    testWidgets('12. tapping Light theme radio sets ThemeMode.light',
        (tester) async {
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      // Use atLeast because "Light" may appear as System subtitle too
      final lightTiles = find.text('Light');
      // The light radio is the second instance (first is the subtitle)
      await tester.tap(lightTiles.last);
      await tester.pump();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SettingsScreen)),
      );
      expect(container.read(themeModeProvider), ThemeMode.light);
    });

    testWidgets('13. tapping Dark theme radio sets ThemeMode.dark',
        (tester) async {
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Dark'));
      await tester.pump();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SettingsScreen)),
      );
      expect(container.read(themeModeProvider), ThemeMode.dark);
    });

    testWidgets('14. logout button opens confirmation dialog',
        (tester) async {
      final mockAuthService = _MockAuthService();

      await tester.binding.setSurfaceSize(const Size(800, 1200));
      await tester.pumpWidget(_wrap(
        const SettingsScreen(),
        extraOverrides: [
          authServiceProvider.overrideWithValue(mockAuthService),
        ],
      ));
      await tester.pumpAndSettle();

      // Tap the logout button via its label text
      await tester.tap(find.text('Sign Out', skipOffstage: false));
      await tester.pumpAndSettle();

      // Confirmation dialog should be visible
      expect(find.text('Are you sure you want to sign out?'), findsOneWidget);

      // Tap the dialog's confirm button (also labeled "Sign Out")
      // Use last because the settings button also has "Sign Out"
      await tester.tap(find.text('Sign Out').last);
      await tester.pumpAndSettle();

      // Verify logout was called
      expect(mockAuthService.logoutCalled, isTrue);
    });

    testWidgets('15. logout dialog cancel does not trigger logout',
        (tester) async {
      final mockAuthService = _MockAuthService();

      await tester.binding.setSurfaceSize(const Size(800, 1200));
      await tester.pumpWidget(_wrap(
        const SettingsScreen(),
        extraOverrides: [
          authServiceProvider.overrideWithValue(mockAuthService),
        ],
      ));
      await tester.pumpAndSettle();

      // Tap the logout button via its label text
      await tester.tap(find.text('Sign Out', skipOffstage: false));
      await tester.pumpAndSettle();

      // Tap Cancel
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      // Logout should NOT have been called
      expect(mockAuthService.logoutCalled, isFalse);
    });

    testWidgets('16. screen does not overflow', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 800));
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
    });

    testWidgets('17. initial locale is English by default', (tester) async {
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SettingsScreen)),
      );
      expect(container.read(localeProvider), const Locale('en'));
    });

    testWidgets('18. initial theme mode is system by default', (tester) async {
      await tester.pumpWidget(_wrap(const SettingsScreen()));
      await tester.pumpAndSettle();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SettingsScreen)),
      );
      expect(container.read(themeModeProvider), ThemeMode.system);
    });
  });
}
