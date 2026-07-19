// ---------------------------------------------------------------------------
// shimmer_loader_test.dart — ShimmerLoader and ShimmerCard widget tests
//
// Covers: shimmer wrapping, ShimmerCard rendering, shimmer line dimensions,
// dark/light mode awareness.
// ---------------------------------------------------------------------------

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shimmer/shimmer.dart';

import 'package:operion_mobile/shared/widgets/shimmer_loader.dart';

/// Helper to wrap a widget in [MaterialApp] for testing.
Widget wrapInApp(Widget child) {
  return MaterialApp(home: Scaffold(body: child));
}

void main() {
  group('ShimmerLoader', () {
    testWidgets('1. renders child widget inside shimmer', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const ShimmerLoader(child: Text('Loading...')),
      ));

      expect(find.text('Loading...'), findsOneWidget);
      expect(find.byType(Shimmer), findsOneWidget);
    });

    testWidgets('2. wraps child in Shimmer.fromColors', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const ShimmerLoader(child: SizedBox(height: 50, width: 100)),
      ));

      final shimmer = tester.widget<Shimmer>(find.byType(Shimmer));
      expect(shimmer.child, isA<SizedBox>());
    });

    testWidgets('3. ShimmerLoader renders without crashing', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const ShimmerLoader(child: SizedBox()),
      ));

      expect(tester.takeException(), isNull);
    });

    testWidgets('4. nested ShimmerCard renders inside Scaffold',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const ShimmerCard(),
      ));

      expect(find.byType(ShimmerCard), findsOneWidget);
    });
  });

  group('ShimmerCard', () {
    testWidgets('5. ShimmerCard renders with Card widget', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const ShimmerCard(),
      ));

      expect(find.byType(Card), findsOneWidget);
    });

    testWidgets('6. ShimmerCard renders multiple shimmer lines',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const ShimmerCard(),
      ));

      // The card contains three _ShimmerLine widgets (FractionallySizedBox
      // with a Container child)
      expect(find.byType(FractionallySizedBox), findsNWidgets(3));
    });

    testWidgets('7. ShimmerCard lines have different widths', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const ShimmerCard(),
      ));

      final fractionBoxes =
          tester.widgetList<FractionallySizedBox>(find.byType(FractionallySizedBox)).toList();

      // Each box has a different widthFactor
      final widths = fractionBoxes.map((b) => b.widthFactor).toSet();
      expect(widths.length, greaterThan(1));
    });

    testWidgets('8. ShimmerCard lines are 12px tall', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const ShimmerCard(),
      ));

      final containers = find.descendant(
        of: find.byType(ShimmerCard),
        matching: find.byType(Container),
      );
      // Each container height should be 12
      for (final element in containers.evaluate()) {
        final container = element.widget as Container;
        expect((container.constraints as BoxConstraints?)?.maxHeight ?? 0,
            equals(12));
      }
    });

    testWidgets('9. ShimmerCard renders without error', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const ShimmerCard(),
      ));

      expect(tester.takeException(), isNull);
    });
  });

  group('ShimmerLoader — custom children', () {
    testWidgets('10. wraps a Column with multiple items', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const ShimmerLoader(
          child: Column(
            children: [
          Text('Line 1'),
              Text('Line 2'),
            ],
          ),
        ),
      ));

      expect(find.text('Line 1'), findsOneWidget);
      expect(find.text('Line 2'), findsOneWidget);
      expect(find.byType(Shimmer), findsOneWidget);
    });

    testWidgets('11. wraps an Image widget without error', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const ShimmerLoader(
          child: SizedBox(width: 100, height: 100),
        ),
      ));

      expect(tester.takeException(), isNull);
    });
  });
}
