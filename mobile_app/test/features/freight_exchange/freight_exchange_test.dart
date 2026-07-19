import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/freight_exchange/screens/freight_exchange_screen.dart';

/// Helper: wraps [child] in MaterialApp with localisations so that
/// `context.loc` works.
Widget wrapFreightExchange() {
  return MaterialApp(
    localizationsDelegates: const [
      AppLocalizations.delegate,
      DefaultMaterialLocalizations.delegate,
      DefaultWidgetsLocalizations.delegate,
    ],
    supportedLocales: AppLocalizations.supportedLocales,
    home: const FreightExchangeScreen(),
  );
}

void main() {
  // ==========================================================================
  // Initial state
  // ==========================================================================
  group('FreightExchangeScreen — initial state', () {
    testWidgets('renders app bar with title', (tester) async {
      await tester.pumpWidget(wrapFreightExchange());
      await tester.pumpAndSettle();

      // Title appears in both AppBar and EmptyState — verify at least one
      expect(find.text('Freight Exchange'), findsAtLeastNWidgets(1));
    });

    testWidgets('renders search text field with search icon', (tester) async {
      await tester.pumpWidget(wrapFreightExchange());
      await tester.pumpAndSettle();

      expect(find.byType(TextFormField), findsOneWidget);
      expect(find.byIcon(LucideIcons.search), findsWidgets);
    });

    testWidgets('shows search hint text', (tester) async {
      await tester.pumpWidget(wrapFreightExchange());
      await tester.pumpAndSettle();

      expect(
        find.text('Search by origin, destination...'),
        findsOneWidget,
      );
    });
  });

  // ==========================================================================
  // Empty state
  // ==========================================================================
  group('FreightExchangeScreen — empty state', () {
    testWidgets('shows empty state with title and subtitle', (tester) async {
      await tester.pumpWidget(wrapFreightExchange());
      await tester.pumpAndSettle();

      expect(find.text('Freight Exchange'), findsAtLeastNWidgets(1));
      expect(
        find.text(
            'Load board data will appear here when the backend is connected.'),
        findsOneWidget,
      );
    });
  });

  // ==========================================================================
  // User interactions
  // ==========================================================================
  group('FreightExchangeScreen — user interactions', () {
    testWidgets('accepts search text input', (tester) async {
      await tester.pumpWidget(wrapFreightExchange());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField), 'Bucharest');
      await tester.pumpAndSettle();

      expect(find.text('Bucharest'), findsOneWidget);
    });

    testWidgets('clears search field when text is removed', (tester) async {
      await tester.pumpWidget(wrapFreightExchange());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField), 'Cluj');
      await tester.pumpAndSettle();

      final textField = tester.widget<TextFormField>(find.byType(TextFormField));
      textField.controller?.clear();
      await tester.pumpAndSettle();

      expect(find.text('Cluj'), findsNothing);
    });
  });
}
