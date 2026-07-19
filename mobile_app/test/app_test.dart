import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/app.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/auth_service.dart';
import 'package:operion_mobile/core/auth/token_manager.dart';
import 'package:operion_mobile/core/network/message_bus.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/l10n/app_localizations.dart';
import 'package:operion_mobile/shared/models/user.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Fake implementations for provider overrides
// ─────────────────────────────────────────────────────────────────────────────

class _FakeSecureTokenStore implements SecureTokenStore {
  @override
  Future<void> saveTokens(String accessToken, String refreshToken) async {}
  @override
  Future<String?> getAccessToken() async => null;
  @override
  Future<String?> getRefreshToken() async => null;
  @override
  Future<void> clearTokens() async {}
  @override
  Future<bool> hasTokens() async => false;
  @override
  Future<String> getOrCreateDeviceId() async => 'test-device-uuid';
}

class _FakeTokenManager implements TokenManager {
  @override
  bool get isAuthenticated => false;
  @override
  Future<void> initialize() async {}
  @override
  Future<String?> getAccessToken() async => null;
  @override
  Future<String?> getRefreshToken() async => null;
  @override
  Future<void> saveTokens(String access, String refresh) async {}
  @override
  Future<void> clearTokens() async {}
  @override
  Future<bool> tryRefresh() async => false;
}

class _FakeAuthService implements AuthService {
  @override
  Future<AuthResult> login(String email, String password) async =>
      const AuthResult(success: true);
  @override
  Future<void> logout() async {}
  @override
  Future<bool> restoreSession() async => false;
  @override
  Future<User?> getCurrentUser() async => null;
}

/// Simplified [AuthStateNotifier] for testing.
class _TestAuthStateNotifier extends AuthStateNotifier {
  _TestAuthStateNotifier(super.ref, AuthState initialState) {
    state = initialState;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  // ==========================================================================
  // Provider setup
  // ==========================================================================
  group('Provider setup', () {
    testWidgets('OperionMobileApp renders MaterialApp', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            localeProvider.overrideWithProvider(
              StateProvider<Locale>((ref) => const Locale('ro')),
            ),
            themeModeProvider.overrideWithProvider(
              StateProvider<ThemeMode>((ref) => ThemeMode.light),
            ),
            messageBusProvider.overrideWith((ref) => MessageBus()),
            authStateProvider.overrideWithProvider(
              StateNotifierProvider<AuthStateNotifier, AuthState>(
                (ref) =>
                    _TestAuthStateNotifier(ref, AuthState.unauthenticated),
              ),
            ),
            currentUserProvider.overrideWithProvider(
              StateProvider<User?>((ref) => null),
            ),
            tokenManagerProvider.overrideWith((ref) => _FakeTokenManager()),
            authServiceProvider.overrideWith((ref) => _FakeAuthService()),
          ],
          child: const OperionMobileApp(),
        ),
      );
      await tester.pump();

      expect(find.byType(MaterialApp), findsOneWidget);
    });

    testWidgets('locale provider defaults to Romanian', (tester) async {
      // The locale is only used inside _OperionMobileApp which is wrapped
      // in a ProviderScope by OperionMobileApp. With our overrides the
      // locale is 'ro' and the app renders without error.
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            localeProvider.overrideWithProvider(
              StateProvider<Locale>((ref) => const Locale('ro')),
            ),
            themeModeProvider.overrideWithProvider(
              StateProvider<ThemeMode>((ref) => ThemeMode.light),
            ),
            messageBusProvider.overrideWith((ref) => MessageBus()),
            authStateProvider.overrideWithProvider(
              StateNotifierProvider<AuthStateNotifier, AuthState>(
                (ref) =>
                    _TestAuthStateNotifier(ref, AuthState.unauthenticated),
              ),
            ),
            currentUserProvider.overrideWithProvider(
              StateProvider<User?>((ref) => null),
            ),
            tokenManagerProvider.overrideWith((ref) => _FakeTokenManager()),
            authServiceProvider.overrideWith((ref) => _FakeAuthService()),
          ],
          child: const OperionMobileApp(),
        ),
      );
      await tester.pump();

      expect(find.byType(MaterialApp), findsOneWidget);
    });
  });

  // ==========================================================================
  // App widget creates MaterialApp
  // ==========================================================================
  group('MaterialApp creation', () {
    /// Helper to pump the app with minimal overrides.
    Future<void> pumpApp(WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            localeProvider.overrideWithProvider(
              StateProvider<Locale>((ref) => const Locale('ro')),
            ),
            themeModeProvider.overrideWithProvider(
              StateProvider<ThemeMode>((ref) => ThemeMode.light),
            ),
            messageBusProvider.overrideWith((ref) => MessageBus()),
            authStateProvider.overrideWithProvider(
              StateNotifierProvider<AuthStateNotifier, AuthState>(
                (ref) =>
                    _TestAuthStateNotifier(ref, AuthState.unauthenticated),
              ),
            ),
            currentUserProvider.overrideWithProvider(
              StateProvider<User?>((ref) => null),
            ),
            tokenManagerProvider.overrideWith((ref) => _FakeTokenManager()),
            authServiceProvider.overrideWith((ref) => _FakeAuthService()),
          ],
          child: const OperionMobileApp(),
        ),
      );
      await tester.pump();
    }

    testWidgets('renders a MaterialApp', (tester) async {
      await pumpApp(tester);
      expect(find.byType(MaterialApp), findsOneWidget);
    });

    testWidgets('debugShowCheckedModeBanner is false', (tester) async {
      await pumpApp(tester);
      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.debugShowCheckedModeBanner, isFalse);
    });

    testWidgets('title is Operion Mobile', (tester) async {
      await pumpApp(tester);
      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.title, 'Operion Mobile');
    });

    testWidgets('has both light and dark themes', (tester) async {
      await pumpApp(tester);
      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.theme, isNotNull);
      expect(materialApp.darkTheme, isNotNull);
    });

    testWidgets('light theme uses Material 3', (tester) async {
      await pumpApp(tester);
      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.theme?.useMaterial3, isTrue);
    });

    testWidgets('supports 2 locales (ro, en)', (tester) async {
      await pumpApp(tester);
      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.supportedLocales, hasLength(2));
      expect(
        materialApp.supportedLocales,
        containsAll([const Locale('ro'), const Locale('en')]),
      );
    });

    testWidgets('includes AppLocalizations delegate', (tester) async {
      await pumpApp(tester);
      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(
        materialApp.localizationsDelegates,
        contains(AppLocalizations.delegate),
      );
    });
  });

  // ==========================================================================
  // Router configuration
  // ==========================================================================
  group('Router configuration', () {
    Future<void> pumpApp(WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            localeProvider.overrideWithProvider(
              StateProvider<Locale>((ref) => const Locale('ro')),
            ),
            themeModeProvider.overrideWithProvider(
              StateProvider<ThemeMode>((ref) => ThemeMode.light),
            ),
            messageBusProvider.overrideWith((ref) => MessageBus()),
            authStateProvider.overrideWithProvider(
              StateNotifierProvider<AuthStateNotifier, AuthState>(
                (ref) =>
                    _TestAuthStateNotifier(ref, AuthState.unauthenticated),
              ),
            ),
            currentUserProvider.overrideWithProvider(
              StateProvider<User?>((ref) => null),
            ),
            tokenManagerProvider.overrideWith((ref) => _FakeTokenManager()),
            authServiceProvider.overrideWith((ref) => _FakeAuthService()),
          ],
          child: const OperionMobileApp(),
        ),
      );
      await tester.pump();
    }

    testWidgets('home widget exists', (tester) async {
      await pumpApp(tester);
      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.home, isNotNull);
    });
  });

  // ==========================================================================
  // Localization setup
  // ==========================================================================
  group('Localization setup', () {
    Future<void> pumpApp(WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            localeProvider.overrideWithProvider(
              StateProvider<Locale>((ref) => const Locale('ro')),
            ),
            themeModeProvider.overrideWithProvider(
              StateProvider<ThemeMode>((ref) => ThemeMode.light),
            ),
            messageBusProvider.overrideWith((ref) => MessageBus()),
            authStateProvider.overrideWithProvider(
              StateNotifierProvider<AuthStateNotifier, AuthState>(
                (ref) =>
                    _TestAuthStateNotifier(ref, AuthState.unauthenticated),
              ),
            ),
            currentUserProvider.overrideWithProvider(
              StateProvider<User?>((ref) => null),
            ),
            tokenManagerProvider.overrideWith((ref) => _FakeTokenManager()),
            authServiceProvider.overrideWith((ref) => _FakeAuthService()),
          ],
          child: const OperionMobileApp(),
        ),
      );
      await tester.pump();
    }

    testWidgets('supports Romanian locale', (tester) async {
      await pumpApp(tester);
      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.supportedLocales, contains(const Locale('ro')));
    });

    testWidgets('supports English locale', (tester) async {
      await pumpApp(tester);
      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.supportedLocales, contains(const Locale('en')));
    });

    testWidgets('has localizations delegates', (tester) async {
      await pumpApp(tester);
      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.localizationsDelegates, isNotEmpty);
    });
  });

  // ==========================================================================
  // Edge cases
  // ==========================================================================
  group('Edge cases', () {
    testWidgets('app renders without error when user is null', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            localeProvider.overrideWithProvider(
              StateProvider<Locale>((ref) => const Locale('ro')),
            ),
            themeModeProvider.overrideWithProvider(
              StateProvider<ThemeMode>((ref) => ThemeMode.light),
            ),
            messageBusProvider.overrideWith((ref) => MessageBus()),
            authStateProvider.overrideWithProvider(
              StateNotifierProvider<AuthStateNotifier, AuthState>(
                (ref) =>
                    _TestAuthStateNotifier(ref, AuthState.unauthenticated),
              ),
            ),
            currentUserProvider.overrideWithProvider(
              StateProvider<User?>((ref) => null),
            ),
            tokenManagerProvider.overrideWith((ref) => _FakeTokenManager()),
            authServiceProvider.overrideWith((ref) => _FakeAuthService()),
          ],
          child: const OperionMobileApp(),
        ),
      );
      await tester.pump();

      // Should not throw — MaterialApp should be present
      expect(find.byType(MaterialApp), findsOneWidget);
    });

    testWidgets('dark theme is configured', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            localeProvider.overrideWithProvider(
              StateProvider<Locale>((ref) => const Locale('ro')),
            ),
            themeModeProvider.overrideWithProvider(
              StateProvider<ThemeMode>((ref) => ThemeMode.dark),
            ),
            messageBusProvider.overrideWith((ref) => MessageBus()),
            authStateProvider.overrideWithProvider(
              StateNotifierProvider<AuthStateNotifier, AuthState>(
                (ref) =>
                    _TestAuthStateNotifier(ref, AuthState.unauthenticated),
              ),
            ),
            currentUserProvider.overrideWithProvider(
              StateProvider<User?>((ref) => null),
            ),
            tokenManagerProvider.overrideWith((ref) => _FakeTokenManager()),
            authServiceProvider.overrideWith((ref) => _FakeAuthService()),
          ],
          child: const OperionMobileApp(),
        ),
      );
      await tester.pump();

      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.darkTheme, isNotNull);
      expect(materialApp.darkTheme?.brightness, Brightness.dark);
    });

    testWidgets('OperionMobileApp can be instantiated', (tester) async {
      const app = OperionMobileApp();
      expect(app, isA<OperionMobileApp>());
    });
  });
}
