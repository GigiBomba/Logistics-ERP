import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:operion_mobile/features/dispatcher/dispatcher_shell.dart';
import 'package:operion_mobile/features/dispatcher/home/dispatcher_home_screen.dart';
import 'package:operion_mobile/features/dispatcher/home/dispatcher_providers.dart';
import 'package:operion_mobile/features/dispatcher/fleet/fleet_map_screen.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/auth_service.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/message_bus.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/shared/models/fleet_position.dart';
import 'package:operion_mobile/features/copilot/providers/copilot_providers.dart';
import 'package:operion_mobile/features/copilot/models/copilot_models.dart';
import 'package:operion_mobile/core/auth/token_manager.dart';
import 'package:operion_mobile/core/network/endpoints/auth_endpoints.dart';
import 'package:operion_mobile/core/network/endpoints/copilot_endpoints.dart';
import 'package:operion_mobile/shared/widgets/offline_banner.dart';

// ---------------------------------------------------------------------------
// Mock / stub implementations
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

/// A stub [ApiClient] that never makes real network calls.
ApiClient _stubApiClient() => ApiClient.create(
      baseUrl: '',
      apiKey: 'test-key',
      getAccessToken: () async => null,
    );

/// Stub [MessageBus].
MessageBus _stubMessageBus() => MessageBus();

/// A stub [AuthService] with no-op logout.
class _StubAuthService extends AuthService {
  _StubAuthService()
      : super(
          _StubAuthEndpoints(),
          _StubTokenManager(),
          _MockSecureTokenStore(),
        );

  @override
  Future<void> logout() async {}
}

class _StubAuthEndpoints extends AuthEndpoints {
  _StubAuthEndpoints() : super(_stubApiClient());
}

class _StubTokenManager extends TokenManager {
  _StubTokenManager()
      : super(
          _MockSecureTokenStore(),
          _StubAuthEndpoints(),
          _stubMessageBus(),
        );
}

// ---------------------------------------------------------------------------
// Provider overrides
// ---------------------------------------------------------------------------

final List<Override> shellOverrides = [
  secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
  biometricServiceProvider.overrideWithValue(_MockBiometricService()),
  apiClientProvider.overrideWithValue(_stubApiClient()),
  messageBusProvider.overrideWithValue(_stubMessageBus()),
  isOfflineProvider.overrideWith((ref) => false),
  dispatcherTabProvider.overrideWith((ref) => 0),
  dispatcherOverviewProvider.overrideWith((ref) async => <String, dynamic>{
        'activeJobs': 5,
        'activeDrivers': 12,
        'openAlerts': 3,
        'vehiclesOnRoad': 8,
        'lastUpdated': DateTime.now().toIso8601String(),
      }),
  fleetPositionsProvider.overrideWith((ref) async => <FleetPosition>[]),
  copilotEndpointsProvider.overrideWithValue(
    CopilotEndpoints(_stubApiClient()),
  ),
  copilotStateProvider.overrideWith((ref) => CopilotStateNotifier(
        ref.watch(copilotEndpointsProvider),
      )),
  authServiceProvider.overrideWithValue(_StubAuthService()),
];

/// Helper: wraps [child] in [ProviderScope] + [MaterialApp] with
/// localisation so that `context.loc` works.
Widget wrapShellScreen(Widget child) {
  return ProviderScope(
    overrides: shellOverrides,
    child: MaterialApp(
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

void main() {
  // ==========================================================================
  // DispatcherShell
  // ==========================================================================
  group('DispatcherShell', () {
    testWidgets('renders bottom navigation with four tabs', (tester) async {
      await tester.pumpWidget(wrapShellScreen(const DispatcherShell()));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(DispatcherShell), findsOneWidget);
      expect(find.byType(BottomNavigationBar), findsOneWidget);

      // Verify the nav bar has 4 items
      final navBar = tester.widget<BottomNavigationBar>(
        find.byType(BottomNavigationBar),
      );
      expect(navBar.items.length, 4);
      // Check tab labels exist
      expect(navBar.items[0].icon, isA<Icon>());
    });

    testWidgets('shows overview screen on initial load (tab 0)',
        (tester) async {
      await tester.pumpWidget(wrapShellScreen(const DispatcherShell()));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tab 0 should render DispatcherHomeScreen
      expect(find.byType(DispatcherHomeScreen), findsOneWidget);
    });

    testWidgets('switching to tab 1 shows fleet map', (tester) async {
      await tester.pumpWidget(wrapShellScreen(const DispatcherShell()));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tap the Fleet Tracker tab (map icon, index 1)
      await tester.tap(find.byIcon(Icons.map_outlined));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(FleetMapScreen), findsOneWidget);
    });

    testWidgets('offline banner is shown when isOfflineProvider is true',
        (tester) async {
      // Override with offline=true for this test
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...shellOverrides,
            isOfflineProvider.overrideWith((ref) => true),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              DefaultMaterialLocalizations.delegate,
              DefaultWidgetsLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const DispatcherShell(),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('You are offline'), findsOneWidget);
    });

    testWidgets('offline banner hidden when online', (tester) async {
      await tester.pumpWidget(wrapShellScreen(const DispatcherShell()));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // OfflineBanner is rendered with isOffline=false
      // AnimatedCrossFade keeps both children in the tree but the
      // offline flag determines the cross-fade state
      final offlineBanner = find.byType(OfflineBanner);
      expect(offlineBanner, findsOneWidget);
      final banner = tester.widget<OfflineBanner>(offlineBanner);
      expect(banner.isOffline, isFalse);
    });
  });
}
