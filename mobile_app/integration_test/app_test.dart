import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:operion_mobile/app.dart';

/// Smoke test: verifies the app can launch without crashing.
///
/// This test uses [IntegrationTestWidgetsFlutterBinding] to run in a
/// real (or headless) device environment and checks that the root
/// [OperionMobileApp] widget renders without throwing.
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('App smoke test', () {
    testWidgets('app launches and renders ModeRouter', (tester) async {
      await tester.pumpWidget(const OperionMobileApp());

      // Allow async initialisation (ProviderScope, locale, session check)
      await tester.pumpAndSettle(const Duration(seconds: 5));

      // The app should render something — at minimum a Scaffold (login screen)
      // or a CircularProgressIndicator (session-restoring state).
      expect(
        find.byType(Scaffold),
        findsOneWidget,
        reason: 'The app should display a Scaffold (login screen) or '
            'a loading indicator on launch.',
      );
    });
  });
}
