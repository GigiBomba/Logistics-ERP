import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/shared/widgets/turn_instruction_banner.dart';

/// Helper to wrap a widget in [MaterialApp] for testing.
Widget wrapInApp(Widget child) {
  return MaterialApp(home: Scaffold(body: child));
}

void main() {
  group('TurnInstructionBanner', () {
    testWidgets('displays instruction text', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(
          instructionText: 'Turn left onto Main St',
        ),
      ));
      expect(find.text('Turn left onto Main St'), findsOneWidget);
    });

    testWidgets('displays distance in meters when < 1000m', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(
          instructionText: 'Continue straight',
          distanceMeters: 450,
        ),
      ));
      expect(find.text('450 m'), findsOneWidget);
    });

    testWidgets('displays distance in km when >= 1000m', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(
          instructionText: 'Keep right',
          distanceMeters: 2350,
        ),
      ));
      expect(find.text('2.4 km'), findsOneWidget);
    });

    testWidgets('displays distance using one decimal for km values',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(
          instructionText: 'Turn right',
          distanceMeters: 1000,
        ),
      ));
      expect(find.text('1.0 km'), findsOneWidget);
    });

    testWidgets('displays ETA text when provided', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(
          instructionText: 'Turn left',
          etaText: '10:30',
        ),
      ));
      expect(find.text('10:30'), findsOneWidget);
    });

    testWidgets('hides ETA when not provided', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(
          instructionText: 'Go straight',
        ),
      ));
      expect(find.text('Go straight'), findsOneWidget);
      // Only the instruction Text widget should exist — no ETA
      expect(
        find.descendant(
          of: find.byType(TurnInstructionBanner),
          matching: find.byType(Text),
        ),
        findsOneWidget,
      );
    });

    testWidgets('renders with all fields provided', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(
          instructionText: 'Merge onto Highway 101',
          distanceMeters: 3200,
          etaText: '14:45',
        ),
      ));
      expect(find.text('Merge onto Highway 101'), findsOneWidget);
      expect(find.text('3.2 km'), findsOneWidget);
      expect(find.text('14:45'), findsOneWidget);
    });

    testWidgets('handles null instruction text gracefully', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(
          distanceMeters: 500,
        ),
      ));
      // Should still display the distance without crashing
      expect(find.text('500 m'), findsOneWidget);
    });

    testWidgets('handles null distance gracefully', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(
          instructionText: 'Turn right',
        ),
      ));
      expect(find.text('Turn right'), findsOneWidget);
    });

    testWidgets('handles all nulls — no crash', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(),
      ));
      // Widget should render an empty container without crashing
      expect(find.byType(TurnInstructionBanner), findsOneWidget);
    });

    testWidgets('distance handles edge case 0 meters', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(
          instructionText: 'Arrived',
          distanceMeters: 0,
        ),
      ));
      expect(find.text('0 m'), findsOneWidget);
    });

    testWidgets('distance handles edge case 999 meters', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(
          instructionText: 'Turn left',
          distanceMeters: 999,
        ),
      ));
      expect(find.text('999 m'), findsOneWidget);
    });

    testWidgets('distance handles edge case 999.9 meters', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(
          instructionText: 'Turn left',
          distanceMeters: 999.9,
        ),
      ));
      expect(find.text('999 m'), findsOneWidget);
    });

    testWidgets('distance handles edge case 1000 meters', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const TurnInstructionBanner(
          instructionText: 'Turn right',
          distanceMeters: 1000,
        ),
      ));
      expect(find.text('1.0 km'), findsOneWidget);
    });
  });
}
