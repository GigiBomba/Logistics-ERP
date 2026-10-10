import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/features/more_hub/screens/more_hub_screen.dart';
import 'package:operion_mobile/l10n/app_localizations.dart';
import 'package:operion_mobile/shared/widgets/app_card.dart';

Widget createTestApp() {
  return ProviderScope(
    overrides: [
      isOfflineProvider.overrideWith((ref) => false),
    ],
    child: MaterialApp(
      localizationsDelegates: [AppLocalizations.delegate],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const MoreHubScreen(),
    ),
  );
}

void main() {
  group('MoreHubScreen', () {
    testWidgets('renders 11 tiles', (tester) async {
      await tester.pumpWidget(createTestApp());
      await tester.pumpAndSettle();

      // Verify the grid exists
      expect(find.byType(GridView), findsOneWidget);

      // Verify 11 tiles are rendered (each _MoreTile renders an AppCard)
      expect(find.byType(AppCard), findsNWidgets(11));
    });
  });
}
