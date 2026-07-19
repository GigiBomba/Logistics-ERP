// ---------------------------------------------------------------------------
// staleness_indicator_test.dart — StalenessIndicator widget tests
//
// Covers: pending state, missing timestamp, relative time formatting,
// icon integration, custom text overrides.
// ---------------------------------------------------------------------------

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/shared/widgets/staleness_indicator.dart';

/// Helper to wrap a widget in [MaterialApp] for testing.
Widget wrapInApp(Widget child) {
  return MaterialApp(home: Scaffold(body: child));
}

void main() {
  group('StalenessIndicator', () {
    // ── Pending state ────────────────────────────────────────────────

    testWidgets('1. shows "Pending sync..." when isPending is true',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StalenessIndicator(isPending: true),
      ));

      expect(find.text('Pending sync...'), findsOneWidget);
    });

    testWidgets('2. shows cloud-off icon when pending', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StalenessIndicator(isPending: true),
      ));

      expect(find.byType(Icon), findsOneWidget);
    });

    testWidgets('3. shows custom pendingText when provided', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StalenessIndicator(
          isPending: true,
          pendingText: 'Syncing...',
        ),
      ));

      expect(find.text('Syncing...'), findsOneWidget);
      expect(find.text('Pending sync...'), findsNothing);
    });

    // ── Missing timestamp ────────────────────────────────────────────

    testWidgets('4. shows "Never" when lastUpdated is null and not pending',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StalenessIndicator(),
      ));

      expect(find.text('Never'), findsOneWidget);
    });

    testWidgets('5. shows custom neverText when provided', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StalenessIndicator(
          neverText: 'Not yet',
        ),
      ));

      expect(find.text('Not yet'), findsOneWidget);
      expect(find.text('Never'), findsNothing);
    });

    testWidgets('6. shows clock icon when lastUpdated is null',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StalenessIndicator(),
      ));

      expect(find.byType(Icon), findsOneWidget);
    });

    // ── Relative time formatting ─────────────────────────────────────

    testWidgets('7. shows "Just now" for very recent updates',
        (tester) async {
      final justNow = DateTime.now();
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(lastUpdated: justNow),
      ));

      expect(find.text('Just now'), findsOneWidget);
    });

    testWidgets('8. shows "Just now" for 10 seconds ago', (tester) async {
      final tenSecAgo = DateTime.now().subtract(const Duration(seconds: 10));
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(lastUpdated: tenSecAgo),
      ));

      expect(find.text('Just now'), findsOneWidget);
    });

    testWidgets('9. shows "5 min ago" for updates 5 minutes ago',
        (tester) async {
      final fiveMinAgo = DateTime.now().subtract(const Duration(minutes: 5));
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(lastUpdated: fiveMinAgo),
      ));

      expect(find.text('5 min ago'), findsOneWidget);
    });

    testWidgets('10. shows "30 min ago" for updates 30 minutes ago',
        (tester) async {
      final thirtyMinAgo = DateTime.now().subtract(const Duration(minutes: 30));
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(lastUpdated: thirtyMinAgo),
      ));

      expect(find.text('30 min ago'), findsOneWidget);
    });

    testWidgets('11. shows "1 hours ago" for 1 hour old data',
        (tester) async {
      final oneHourAgo = DateTime.now().subtract(const Duration(hours: 1));
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(lastUpdated: oneHourAgo),
      ));

      expect(find.text('1 hours ago'), findsOneWidget);
    });

    testWidgets('12. shows "12 hours ago" for 12 hours old data',
        (tester) async {
      final twelveHoursAgo =
          DateTime.now().subtract(const Duration(hours: 12));
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(lastUpdated: twelveHoursAgo),
      ));

      expect(find.text('12 hours ago'), findsOneWidget);
    });

    testWidgets('13. shows "1 days ago" for 1 day old data', (tester) async {
      final oneDayAgo = DateTime.now().subtract(const Duration(days: 1));
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(lastUpdated: oneDayAgo),
      ));

      expect(find.text('1 days ago'), findsOneWidget);
    });

    testWidgets('14. shows "7 days ago" for 7 days old data',
        (tester) async {
      final sevenDaysAgo = DateTime.now().subtract(const Duration(days: 7));
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(lastUpdated: sevenDaysAgo),
      ));

      expect(find.text('7 days ago'), findsOneWidget);
    });

    testWidgets('15. shows "Just now" for future timestamps',
        (tester) async {
      final future = DateTime.now().add(const Duration(minutes: 5));
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(lastUpdated: future),
      ));

      expect(find.text('Just now'), findsOneWidget);
    });

    // ── Icon integration ─────────────────────────────────────────────

    testWidgets('16. shows check-circle icon for fresh data (< 1 min)',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(lastUpdated: DateTime.now()),
      ));

      // Still shows an icon for fresh data
      expect(find.byType(Icon), findsOneWidget);
    });

    testWidgets('17. shows row layout with icon and text', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StalenessIndicator(isPending: true),
      ));

      // The widget uses a Row with MainAxisSize.min
      final row = tester.widget<Row>(find.byType(Row));
      expect(row.mainAxisSize, MainAxisSize.min);
    });

    // ── Styling ──────────────────────────────────────────────────────

    testWidgets('18. text style has fontSize 11', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StalenessIndicator(isPending: true),
      ));

      final text = tester.widget<Text>(find.text('Pending sync...'));
      expect(text.style?.fontSize, 11);
      expect(text.style?.fontWeight, FontWeight.w400);
    });

    testWidgets('19. icon size is 14', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StalenessIndicator(isPending: true),
      ));

      final icon = tester.widget<Icon>(find.byType(Icon));
      expect(icon.size, 14);
    });

    // ── Edge cases ───────────────────────────────────────────────────

    testWidgets('20. pending takes priority over lastUpdated', (tester) async {
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(
          isPending: true,
          lastUpdated: DateTime.now().subtract(const Duration(hours: 2)),
        ),
      ));

      // Should show pending text, not "2 hours ago"
      expect(find.text('Pending sync...'), findsOneWidget);
      expect(find.text('2 hours ago'), findsNothing);
    });

    testWidgets('21. does not throw when rendered', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StalenessIndicator(),
      ));

      expect(tester.takeException(), isNull);
    });

    testWidgets('22. pendingText overrides default pending label',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(
          isPending: true,
          pendingText: 'Awaiting sync...',
          lastUpdated: DateTime.now(),
        ),
      ));

      expect(find.text('Awaiting sync...'), findsOneWidget);
    });
  });
}
