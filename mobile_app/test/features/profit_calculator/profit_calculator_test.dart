import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/profit_calculator/screens/profit_calculator_screen.dart';

/// Helper: wraps [child] in MaterialApp with localisations so that
/// `context.loc` works.
Widget wrapProfitCalculator() {
  return MaterialApp(
    localizationsDelegates: const [
      AppLocalizations.delegate,
      DefaultMaterialLocalizations.delegate,
      DefaultWidgetsLocalizations.delegate,
    ],
    supportedLocales: AppLocalizations.supportedLocales,
    home: const ProfitCalculatorScreen(),
  );
}

void main() {
  // ==========================================================================
  // Initial state
  // ==========================================================================
  group('ProfitCalculatorScreen — initial state', () {
    testWidgets('renders app bar with title', (tester) async {
      await tester.pumpWidget(wrapProfitCalculator());
      await tester.pumpAndSettle();

      expect(find.text('Profit Calculator'), findsOneWidget);
    });

    testWidgets('renders all five input fields', (tester) async {
      await tester.pumpWidget(wrapProfitCalculator());
      await tester.pumpAndSettle();

      expect(find.byType(TextFormField), findsNWidgets(5));
    });

    testWidgets('renders calculate button', (tester) async {
      await tester.pumpWidget(wrapProfitCalculator());
      await tester.pumpAndSettle();

      expect(find.text('Calculate'), findsOneWidget);
    });

    testWidgets('does not show results initially', (tester) async {
      await tester.pumpWidget(wrapProfitCalculator());
      await tester.pumpAndSettle();

      expect(find.text('Total Costs'), findsNothing);
      expect(find.text('Profit'), findsNothing);
      expect(find.text('Profit Margin'), findsNothing);
    });
  });

  // ==========================================================================
  // Calculation
  // ==========================================================================
  group('ProfitCalculatorScreen — calculation', () {
    testWidgets('shows correct result after valid input', (tester) async {
      await tester.pumpWidget(wrapProfitCalculator());
      await tester.pumpAndSettle();

      // Revenue: 10000, Fuel: 2000, Toll: 1000, Maint: 500, Driver: 1500
      final fields = find.byType(TextFormField);
      await tester.enterText(fields.at(0), '10000');
      await tester.enterText(fields.at(1), '2000');
      await tester.enterText(fields.at(2), '1000');
      await tester.enterText(fields.at(3), '500');
      await tester.enterText(fields.at(4), '1500');
      await tester.pumpAndSettle();

      await tester.tap(find.text('Calculate'));
      await tester.pumpAndSettle();

      // Total costs: 2000 + 1000 + 500 + 1500 = 5000
      // Both total costs and profit show $5000.00 (revenue 10000 - costs 5000)
      expect(find.text('\$5000.00'), findsAtLeastNWidgets(1));
      // Profit margin: 5000/10000 * 100 = 50.00%
      // Profit margin: 5000/10000 * 100 = 50.00%
      expect(find.text('50.00%'), findsOneWidget);
    });

    testWidgets('shows negative profit when costs exceed revenue',
        (tester) async {
      await tester.pumpWidget(wrapProfitCalculator());
      await tester.pumpAndSettle();

      final fields = find.byType(TextFormField);
      await tester.enterText(fields.at(0), '3000');
      await tester.enterText(fields.at(1), '2000');
      await tester.enterText(fields.at(2), '1000');
      await tester.enterText(fields.at(3), '500');
      await tester.enterText(fields.at(4), '1000');
      await tester.pumpAndSettle();

      await tester.tap(find.text('Calculate'));
      await tester.pumpAndSettle();

      // Profit should be negative: 3000 - 4500 = -1500
      expect(find.text('\$-1500.00'), findsOneWidget);
    });

    testWidgets('handles empty fields as zero', (tester) async {
      await tester.pumpWidget(wrapProfitCalculator());
      await tester.pumpAndSettle();

      // Only fill revenue
      final fields = find.byType(TextFormField);
      await tester.enterText(fields.at(0), '5000');
      await tester.pumpAndSettle();

      await tester.tap(find.text('Calculate'));
      await tester.pumpAndSettle();

      // All costs default to 0, profit = 5000
      expect(find.text('\$0.00'), findsAtLeastNWidgets(1)); // total costs
      expect(find.text('\$5000.00'), findsAtLeastNWidgets(1)); // profit
      expect(find.text('100.00%'), findsOneWidget); // margin
    });
  });

  // ==========================================================================
  // Result rows rendering
  // ==========================================================================
  group('ProfitCalculatorScreen — result display', () {
    testWidgets('shows result labels after calculation', (tester) async {
      await tester.pumpWidget(wrapProfitCalculator());
      await tester.pumpAndSettle();

      final fields = find.byType(TextFormField);
      await tester.enterText(fields.at(0), '10000');
      await tester.enterText(fields.at(1), '2000');
      await tester.pumpAndSettle();

      await tester.tap(find.text('Calculate'));
      await tester.pumpAndSettle();

      expect(find.text('Total Costs'), findsOneWidget);
      expect(find.text('Profit'), findsOneWidget);
      expect(find.text('Profit Margin'), findsOneWidget);
    });
  });
}
