import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/driver/models/route_share_geometry.dart';
import 'package:operion_mobile/features/driver/route_share/providers/route_share_providers.dart';
import 'package:operion_mobile/features/driver/route_share/screens/route_share_nav_screen.dart';

// ── Fake geometry data ──────────────────────────────────────────────────────

RouteShareGeometry _testGeometry({int pointCount = 3}) {
  return RouteShareGeometry(
    transportId: 't-001',
    points: List.generate(
      pointCount,
      (i) => RoutePoint(lat: 44.42 + i * 0.01, lng: 26.10 + i * 0.01),
    ),
    instructions: pointCount > 0
        ? [
            const RouteInstruction(textKey: 'Turn left', distanceMeters: 500, pointIndex: 0),
            const RouteInstruction(textKey: 'Turn right', distanceMeters: 300, pointIndex: 1),
          ]
        : const [],
    totalDistanceMeters: 12450.0,
    totalDurationSeconds: 840,
    generatedAt: DateTime.now(),
    ttlSeconds: 300,
  );
}

// ── Provider overrides ─────────────────────────────────────────────────────

/// Builds the widget under test with controllable geometry and offline state.
/// NOTE: Populated-state tests that render FlutterMap are avoided because
/// TileLayer makes HTTP requests that raise unhandled exceptions in the
/// test environment. Loading/error/empty states (which have no FlutterMap)
/// are fully tested.
Widget wrapRouteShareScreen({
  RouteShareGeometry? geometry,
  bool isLoading = false,
}) {
  return ProviderScope(
    overrides: [
      routeShareGeometryProvider.overrideWith(
        (ref) async {
          if (isLoading) {
            await Completer<RouteShareGeometry>().future;
          }
          if (geometry == null) throw Exception('No route data');
          return geometry;
        },
      ),
    ],
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const RouteShareNavScreen(),
    ),
  );
}

void main() {
  // ==========================================================================
  // Loading state
  // ==========================================================================
  group('RouteShareNavScreen — loading state', () {
    testWidgets('shows CircularProgressIndicator while loading', (tester) async {
      await tester.pumpWidget(wrapRouteShareScreen(isLoading: true));
      await tester.pump(); // Don't pumpAndSettle — Completer never completes

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });
  });

  // ==========================================================================
  // Error state
  // ==========================================================================
  group('RouteShareNavScreen — error state', () {
    testWidgets('shows error message and retry button on fetch failure',
        (tester) async {
      await tester.pumpWidget(wrapRouteShareScreen());
      await tester.pumpAndSettle();

      // Retry icon button
      expect(find.byIcon(Icons.refresh), findsOneWidget);

      // Error text from localizations (English)
      expect(find.text('An error occurred'), findsOneWidget);
    });

    testWidgets('tapping retry re-triggers the provider', (tester) async {
      await tester.pumpWidget(wrapRouteShareScreen());
      await tester.pumpAndSettle();

      // Error state visible
      expect(find.text('An error occurred'), findsOneWidget);

      // Tap retry
      await tester.tap(find.byIcon(Icons.refresh));
      await tester.pumpAndSettle();

      // Provider re-evaluates — since geometry is still null it errors again
      expect(find.text('An error occurred'), findsOneWidget);
    });
  });

  // ==========================================================================
  // Empty state (no route points)
  // ==========================================================================
  group('RouteShareNavScreen — empty state', () {
    testWidgets('shows empty route view when geometry has no points',
        (tester) async {
      final emptyGeometry = _testGeometry(pointCount: 0);
      await tester.pumpWidget(wrapRouteShareScreen(geometry: emptyGeometry));
      await tester.pumpAndSettle();

      // Empty state text from localizations (English)
      expect(find.text('No route data'), findsOneWidget);
      expect(
        find.text(
            'Route information is not yet available for this transport.'),
        findsOneWidget,
      );
    });
  });

  // ==========================================================================
  // Populated state — basic rendering only (avoids FlutterMap tile loads)
  // ==========================================================================
  group('RouteShareNavScreen — populated state', () {
    testWidgets('renders without crash when geometry is provided',
        (tester) async {
      // Suppress network image errors from FlutterMap tile loading
      final errors = <String>[];
      final originalHandler = FlutterError.onError;
      FlutterError.onError = (details) {
        if (details.exceptionAsString().contains('tile.openstreetmap')) {
          errors.add(details.exceptionAsString());
        } else {
          originalHandler?.call(details);
        }
      };
      addTearDown(() => FlutterError.onError = originalHandler);

      final geometry = _testGeometry();
      await tester.pumpWidget(wrapRouteShareScreen(geometry: geometry));
      await tester.pump();
      await tester.pump();

      // Screen rendered without crashing
      expect(find.byType(Scaffold), findsOneWidget);
      expect(errors, isNotEmpty); // tile errors were caught
    });
  });
}
