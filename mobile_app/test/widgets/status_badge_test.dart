// ---------------------------------------------------------------------------
// status_badge_test.dart — StatusBadge widget tests
//
// Covers: all status keys render correct labels, custom label override,
// fallback for unknown keys, container styling, and color integration.
// ---------------------------------------------------------------------------

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/shared/widgets/status_badge.dart';

/// Helper to wrap a widget in [MaterialApp] for testing.
Widget wrapInApp(Widget child) {
  return MaterialApp(home: Scaffold(body: child));
}

void main() {
  group('StatusBadge', () {
    // ── Known status rendering ───────────────────────────────────────

    testWidgets('1. renders planned status with Romanian label',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'planned'),
      ));

      expect(find.text('Planificat'), findsOneWidget);
    });

    testWidgets('2. renders delivered status', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'delivered'),
      ));

      expect(find.text('Livrat'), findsOneWidget);
    });

    testWidgets('3. renders in_progress status', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'in_progress'),
      ));

      expect(find.text('În curs'), findsOneWidget);
    });

    testWidgets('4. renders in_transit status same as in_progress',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'in_transit'),
      ));

      expect(find.text('În curs'), findsOneWidget);
    });

    testWidgets('5. renders cancelled status', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'cancelled'),
      ));

      expect(find.text('Anulat'), findsOneWidget);
    });

    testWidgets('6. renders overdue status', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'overdue'),
      ));

      expect(find.text('Restant'), findsOneWidget);
    });

    testWidgets('7. renders maintenance status', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'maintenance'),
      ));

      expect(find.text('Mentenanță'), findsOneWidget);
    });

    testWidgets('8. renders loading status', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'loading'),
      ));

      expect(find.text('Se încarcă'), findsOneWidget);
    });

    testWidgets('9. renders invoiced status', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'invoiced'),
      ));

      expect(find.text('Facturat'), findsOneWidget);
    });

    testWidgets('10. renders paid status', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'paid'),
      ));

      expect(find.text('Plătit'), findsOneWidget);
    });

    // ── Unknown status key ───────────────────────────────────────────

    testWidgets('11. renders unknown status key as fallback text',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'unknown_status'),
      ));

      expect(find.text('unknown_status'), findsOneWidget);
    });

    testWidgets('12. renders empty string key as fallback', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: ''),
      ));

      expect(find.text(''), findsOneWidget);
    });

    // ── Custom label override ────────────────────────────────────────

    testWidgets('13. renders with custom label override', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'delivered', label: 'Custom Label'),
      ));

      expect(find.text('Custom Label'), findsOneWidget);
      // Default label should not appear
      expect(find.text('Livrat'), findsNothing);
    });

    testWidgets('14. custom label on unknown key shows custom text',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'unknown', label: 'Custom Unknown'),
      ));

      expect(find.text('Custom Unknown'), findsOneWidget);
    });

    // ── Container styling ────────────────────────────────────────────

    testWidgets('15. badge is rendered as a Container', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'delivered'),
      ));

      expect(find.byType(Container), findsOneWidget);
    });

    testWidgets('16. container has border radius', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'delivered'),
      ));

      final container = tester.widget<Container>(find.byType(Container));
      final decoration = container.decoration as BoxDecoration;
      expect(decoration.borderRadius, isNotNull);
    });

    testWidgets('17. text style has fontSize 11 and weight w600',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'delivered'),
      ));

      final text = tester.widget<Text>(find.text('Livrat'));
      expect(text.style?.fontSize, 11);
      expect(text.style?.fontWeight, FontWeight.w600);
    });

    // ── Color coding ─────────────────────────────────────────────────

    testWidgets('18. delivered uses success colors', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'delivered'),
      ));

      final container = tester.widget<Container>(find.byType(Container));
      final decoration = container.decoration as BoxDecoration;
      // successSubtle = Color(0x2910B981)
      expect(decoration.color, const Color(0x2910B981));
    });

    testWidgets('19. cancelled uses neutral colors', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'cancelled'),
      ));

      final container = tester.widget<Container>(find.byType(Container));
      final decoration = container.decoration as BoxDecoration;
      // neutralSubtle = Color(0x298E8EA0)
      expect(decoration.color, const Color(0x298E8EA0));
    });

    testWidgets('20. overdue uses error colors', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'overdue'),
      ));

      final container = tester.widget<Container>(find.byType(Container));
      final decoration = container.decoration as BoxDecoration;
      // errorSubtle = Color(0x29EF4444)
      expect(decoration.color, const Color(0x29EF4444));
    });

    testWidgets('21. unknown key uses neutral fallback colors',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'nonexistent'),
      ));

      final container = tester.widget<Container>(find.byType(Container));
      final decoration = container.decoration as BoxDecoration;
      // neutralSubtle = Color(0x298E8EA0)
      expect(decoration.color, const Color(0x298E8EA0));
    });

    // ── Edge cases ───────────────────────────────────────────────────

    testWidgets('22. all status keys render without error', (tester) async {
      const keys = [
        'delivered', 'planned', 'in_progress', 'in_transit',
        'cancelled', 'overdue', 'maintenance', 'loading',
        'invoiced', 'paid',
      ];

      for (final key in keys) {
        await tester.pumpWidget(wrapInApp(
          StatusBadge(statusKey: key),
        ));
        await tester.pump();
        expect(tester.takeException(), isNull,
            reason: 'StatusBadge with key "$key" should not throw');
      }
    });

    testWidgets('23. does not throw when rendered', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'planned'),
      ));

      expect(tester.takeException(), isNull);
    });
  });
}
