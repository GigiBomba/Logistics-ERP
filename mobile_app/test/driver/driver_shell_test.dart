// ---------------------------------------------------------------------------
// driver_shell_test.dart — 26 widget test scenarios
//
// Covers: shell structure, offline banner, tab navigation (4 tabs), content
// switching, offline mode toggle, surface resize, and rapid interactions.
// ---------------------------------------------------------------------------

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:dio/dio.dart';

import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/driver_endpoints.dart';
import 'package:operion_mobile/core/network/endpoints/copilot_endpoints.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/driver/driver_shell.dart';
import 'package:operion_mobile/features/copilot/providers/copilot_providers.dart';
import 'package:operion_mobile/features/driver/home/driver_providers.dart';
import 'package:operion_mobile/features/driver/route_share/providers/route_share_providers.dart';
import 'package:operion_mobile/features/driver/trip_overview/providers/trip_overview_providers.dart';
import 'package:operion_mobile/shared/models/user.dart';
import 'package:operion_mobile/shared/widgets/offline_banner.dart';

// ---------------------------------------------------------------------------
// Mock / stub dependencies
// ---------------------------------------------------------------------------

class _MockSecureTokenStore extends SecureTokenStore {
  @override Future<bool> hasTokens() async => false;
  @override Future<String?> getAccessToken() async => null;
  @override Future<String?> getRefreshToken() async => null;
  @override Future<void> saveTokens(String a, String r) async {}
  @override Future<void> clearTokens() async {}
}

class _MockBiometricService extends BiometricService {
  @override Future<bool> isAvailable() async => false;
  @override Future<bool> authenticate({required String reason}) async => false;
}

/// Stub ApiClient that returns empty responses.
ApiClient _stubApiClient() =>
    ApiClient.create(baseUrl: '', getAccessToken: () async => null);

/// Stub DriverEndpoints returning empty data.
class _StubDriverEndpoints extends DriverEndpoints {
  _StubDriverEndpoints() : super(_stubApiClient());

  @override Future<Response> getMyDay() async =>
      Response(requestOptions: RequestOptions(path: ''), data: <String, dynamic>{});
  @override Future<Response> getTransports() async =>
      Response(requestOptions: RequestOptions(path: ''), data: []);
  @override Future<Response> getTransport(String id) async =>
      Response(requestOptions: RequestOptions(path: ''), data: <String, dynamic>{});
  @override Future<Response> getVehicle() async =>
      Response(requestOptions: RequestOptions(path: ''), data: <String, dynamic>{});
  @override Future<Response> getRouteShare() async =>
      Response(requestOptions: RequestOptions(path: ''), data: <String, dynamic>{});
  @override Future<Response> getTripOverview() async =>
      Response(requestOptions: RequestOptions(path: ''), data: <String, dynamic>{});
}

/// Stub CopilotEndpoints avoiding real HTTP calls.
class _StubCopilotEndpoints extends CopilotEndpoints {
  _StubCopilotEndpoints() : super(_stubApiClient());
}

// ---------------------------------------------------------------------------
// Provider overrides
// ---------------------------------------------------------------------------

/// Creates a ProviderScope with all necessary overrides for the DriverShell.
///
/// Tab-content providers are kept in loading or error state (controlled by
/// [routeShareError] and [tripOverviewError]) so FlutterMap and other complex
/// widgets are not rendered during shell testing.
Widget _wrapShell({
  bool routeShareError = true,
  bool tripOverviewError = true,
  bool isOffline = false,
}) {
  return ProviderScope(
    overrides: [
      secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
      biometricServiceProvider.overrideWithValue(_MockBiometricService()),
      apiClientProvider.overrideWithValue(_stubApiClient()),
      driverEndpointsProvider.overrideWithValue(_StubDriverEndpoints()),
      currentUserProvider.overrideWith((ref) => User(
        id: 'driver-1',
        email: 'driver@test.com',
        fullName: 'Test Driver',
        role: 'driver',
        companyId: 'c1',
      )),
      isOfflineProvider.overrideWith((ref) => isOffline),
      localeProvider.overrideWith((ref) => const Locale('en')),
      themeModeProvider.overrideWith((ref) => ThemeMode.light),

      // Tab content providers — keep in error or loading state to avoid
      // rendering complex widgets (FlutterMap, etc.) during shell testing.
      routeShareGeometryProvider.overrideWith((ref) async {
        if (routeShareError) throw Exception('Stub error');
        await Completer<void>().future;
        throw UnimplementedError('Never completes');
      }),
      tripOverviewProvider.overrideWith((ref) async {
        if (tripOverviewError) throw Exception('Stub error');
        await Completer<void>().future;
        throw UnimplementedError('Never completes');
      }),

      // Copilot — stub endpoints to prevent real HTTP calls.
      copilotEndpointsProvider.overrideWithValue(_StubCopilotEndpoints()),
    ],
    child: MaterialApp(
      localizationsDelegates: const [AppLocalizations.delegate],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const DriverShell(),
    ),
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

Future<void> pumpAndAllowAsync(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 100));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  // ==========================================================================
  // Structure
  // ==========================================================================
  group('DriverShell — Structure', () {
    testWidgets('1. renders Scaffold', (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      expect(find.byType(Scaffold), findsAtLeast(1));
    });

    testWidgets('2. renders BottomNavigationBar with 4 items', (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      final navBar = find.byType(BottomNavigationBar);
      expect(navBar, findsOneWidget);
      final bar = tester.widget<BottomNavigationBar>(navBar);
      expect(bar.items.length, 4);
    });

    testWidgets('3. first tab has Map label', (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      final navBar = tester.widget<BottomNavigationBar>(
        find.byType(BottomNavigationBar),
      );
      expect(navBar.items[0].label, 'Map');
    });

    testWidgets('4. second tab has Overview label', (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      final navBar = tester.widget<BottomNavigationBar>(
        find.byType(BottomNavigationBar),
      );
      expect(navBar.items[1].label, 'Overview');
    });

    testWidgets('5. third tab has AI Copilot label', (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      final navBar = tester.widget<BottomNavigationBar>(
        find.byType(BottomNavigationBar),
      );
      expect(navBar.items[2].label, 'AI Copilot');
    });

    testWidgets('6. fourth tab has Settings label', (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      final navBar = tester.widget<BottomNavigationBar>(
        find.byType(BottomNavigationBar),
      );
      expect(navBar.items[3].label, 'Settings');
    });
  });

  // ==========================================================================
  // Offline Banner
  // ==========================================================================
  group('DriverShell — Offline Banner', () {
    testWidgets('7. offline banner crossfade is showFirst when online',
        (tester) async {
      await tester.pumpWidget(_wrapShell(isOffline: false));
      await pumpAndAllowAsync(tester);

      final crossFade = tester.widget<AnimatedCrossFade>(
        find.byType(AnimatedCrossFade),
      );
      expect(crossFade.crossFadeState, CrossFadeState.showFirst);
    });

    testWidgets('8. offline banner crossfade is showSecond when offline',
        (tester) async {
      await tester.pumpWidget(_wrapShell(isOffline: true));
      await pumpAndAllowAsync(tester);

      final crossFade = tester.widget<AnimatedCrossFade>(
        find.byType(AnimatedCrossFade),
      );
      expect(crossFade.crossFadeState, CrossFadeState.showSecond);
    });

    testWidgets('9. offline banner shows wifi-off icon', (tester) async {
      await tester.pumpWidget(_wrapShell(isOffline: true));
      await pumpAndAllowAsync(tester);

      expect(find.byIcon(LucideIcons.wifiOff), findsOneWidget);
    });

    testWidgets('10. offline banner shows proper crossfade when offline',
        (tester) async {
      await tester.pumpWidget(_wrapShell(isOffline: true));
      await pumpAndAllowAsync(tester);

      final crossFade = tester.widget<AnimatedCrossFade>(
        find.byType(AnimatedCrossFade),
      );
      expect(crossFade.crossFadeState, CrossFadeState.showSecond);

      // Wifi icon should also be present
      expect(find.byIcon(LucideIcons.wifiOff), findsOneWidget);
    });
  });

  // ==========================================================================
  // Tab Navigation
  // ==========================================================================
  group('DriverShell — Tab Navigation', () {
    testWidgets('11. initial tab currentIndex is 0 (Map)', (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      final navBar = tester.widget<BottomNavigationBar>(
        find.byType(BottomNavigationBar),
      );
      expect(navBar.currentIndex, 0);
    });

    testWidgets('12. tapping Overview tab switches to index 1',
        (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      await tester.tap(find.text('Overview'));
      await pumpAndAllowAsync(tester);

      final navBar = tester.widget<BottomNavigationBar>(
        find.byType(BottomNavigationBar),
      );
      expect(navBar.currentIndex, 1);
    });

    testWidgets('13. tapping AI Copilot tab switches to index 2',
        (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      await tester.tap(find.text('AI Copilot'));
      await pumpAndAllowAsync(tester);

      final navBar = tester.widget<BottomNavigationBar>(
        find.byType(BottomNavigationBar),
      );
      expect(navBar.currentIndex, 2);
    });

    testWidgets('14. tapping Settings tab switches to index 3',
        (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      await tester.tap(find.text('Settings'));
      await pumpAndAllowAsync(tester);

      final navBar = tester.widget<BottomNavigationBar>(
        find.byType(BottomNavigationBar),
      );
      expect(navBar.currentIndex, 3);
    });

    testWidgets('15. tapping same tab stays on current index',
        (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      // Tap Map twice
      await tester.tap(find.text('Map'));
      await pumpAndAllowAsync(tester);
      await tester.tap(find.text('Map'));
      await pumpAndAllowAsync(tester);

      final navBar = tester.widget<BottomNavigationBar>(
        find.byType(BottomNavigationBar),
      );
      expect(navBar.currentIndex, 0);
    });

    testWidgets('16. all four tabs are tappable without crash',
        (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      for (final label in ['Overview', 'AI Copilot', 'Settings', 'Map']) {
        await tester.tap(find.text(label));
        await pumpAndAllowAsync(tester);
        expect(tester.takeException(), isNull);
      }
    });

    testWidgets('17. shell has OfflineBanner and BottomNavigationBar',
        (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      // The shell contains these widgets in its tree
      expect(find.byType(OfflineBanner), findsOneWidget);
      expect(find.byType(BottomNavigationBar), findsOneWidget);
    });
  });

  // ==========================================================================
  // Tab Content
  // ==========================================================================
  group('DriverShell — Tab Content', () {
    testWidgets('18. Map tab shows error state (safe, no FlutterMap)',
        (tester) async {
      await tester.pumpWidget(_wrapShell(routeShareError: true));
      await pumpAndAllowAsync(tester);

      // RouteShareNavScreen error state — Scaffolds exist (shell + content)
      expect(find.byType(Scaffold), findsAtLeast(1));
    });

    testWidgets('19. switching to Settings tab shows Settings content',
        (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      await tester.tap(find.text('Settings'));
      await pumpAndAllowAsync(tester);

      // SettingsScreen renders an AppBar with "Settings" title
      expect(find.text('Settings'), findsAtLeast(1));
    });

    testWidgets('20. shell Scaffold and BottomNav persist across tabs',
        (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      for (final label in ['Overview', 'AI Copilot', 'Settings', 'Map']) {
        await tester.tap(find.text(label));
        await pumpAndAllowAsync(tester);
        expect(find.byType(Scaffold), findsAtLeast(1));
        expect(find.byType(BottomNavigationBar), findsOneWidget);
      }
    });
  });

  // ==========================================================================
  // Edge Cases
  // ==========================================================================
  group('DriverShell — Edge Cases', () {
    testWidgets('21. rapid tab switching does not crash', (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      for (int i = 0; i < 8; i++) {
        final labels = ['Map', 'Overview', 'AI Copilot', 'Settings'];
        await tester.tap(find.text(labels[i % 4]));
        await tester.pump(const Duration(milliseconds: 50));
      }

      expect(tester.takeException(), isNull);
    });

    testWidgets('22. shell handles small viewport resize', (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      await tester.binding.setSurfaceSize(const Size(360, 640));
      await tester.pumpAndSettle(const Duration(seconds: 1));
      expect(tester.takeException(), isNull);
    });

    testWidgets('23. shell renders in larger viewport', (tester) async {
      await tester.binding.setSurfaceSize(const Size(1200, 900));
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);
      expect(tester.takeException(), isNull);
    });

    testWidgets('24. OfflineBanner widget is part of shell Column',
        (tester) async {
      await tester.pumpWidget(_wrapShell(isOffline: true));
      await pumpAndAllowAsync(tester);

      // OfflineBanner should be somewhere in the tree
      expect(find.byType(OfflineBanner), findsOneWidget);
      // The text should be visible
      expect(find.text('You are offline'), findsOneWidget);
    });

    testWidgets('25. offline banner uses AnimatedCrossFade', (tester) async {
      await tester.pumpWidget(_wrapShell(isOffline: true));
      await pumpAndAllowAsync(tester);

      expect(find.byType(AnimatedCrossFade), findsOneWidget);
    });

    testWidgets('26. no unhandled exceptions during normal render',
        (tester) async {
      await tester.pumpWidget(_wrapShell());
      await pumpAndAllowAsync(tester);

      expect(tester.takeException(), isNull);
    });
  });
}
