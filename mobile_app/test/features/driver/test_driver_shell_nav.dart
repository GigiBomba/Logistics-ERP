import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/driver/driver_shell.dart';
import 'package:operion_mobile/shared/widgets/offline_banner.dart';

Widget buildDriverShell({bool offline = false}) {
  return ProviderScope(
    overrides: [
      currentUserProvider.overrideWith((ref) => null),
      isOfflineProvider.overrideWith((ref) => offline),
    ],
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const DriverShell(),
    ),
  );
}

void main() {
  group('DriverShell navigation', () {
    testWidgets('renders DriverShell without errors', (tester) async {
      await tester.pumpWidget(buildDriverShell());
      // Should not throw
      expect(tester.takeException(), isNull);
    });

    testWidgets('renders exactly 4 bottom navigation items', (tester) async {
      await tester.pumpWidget(buildDriverShell());
      await tester.pumpAndSettle();

      final navBar = tester.widget<BottomNavigationBar>(
        find.byType(BottomNavigationBar),
      );
      expect(navBar.items.length, 4);
    });

    testWidgets('shows OfflineBanner at the top', (tester) async {
      await tester.pumpWidget(buildDriverShell(offline: true));
      await tester.pumpAndSettle();

      expect(find.byType(OfflineBanner), findsOneWidget);
    });
  });
}
