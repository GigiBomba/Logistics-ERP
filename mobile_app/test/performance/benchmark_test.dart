import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/shared/widgets/app_button.dart';
import 'package:operion_mobile/shared/widgets/app_card.dart';
import 'package:operion_mobile/shared/widgets/app_text_field.dart';
import 'package:operion_mobile/shared/widgets/empty_state.dart';

/// Helper to wrap a widget in [MaterialApp] for testing.
Widget wrapInApp(Widget child) {
  return MaterialApp(home: Scaffold(body: Center(child: child)));
}

/// Measures the average build time of [builder] over [iterations] runs.
Future<double> measureBuildTime(
  WidgetTester tester,
  Widget Function() builder, {
  int iterations = 10,
}) async {
  final durations = <int>[];

  for (int i = 0; i < iterations; i++) {
    // Rebuild to a plain container first to clear the previous widget.
    await tester.pumpWidget(wrapInApp(const SizedBox.shrink()));
    await tester.pumpAndSettle();

    final stopwatch = Stopwatch()..start();
    await tester.pumpWidget(wrapInApp(builder()));
    await tester.pumpAndSettle();
    stopwatch.stop();
    durations.add(stopwatch.elapsedMicroseconds);
  }

  final total = durations.reduce((a, b) => a + b);
  return total / iterations;
}

void main() {
  // Print header
  setUpAll(() {
    print('═══════════════════════════════════════════════');
    print('  Widget Build Time Benchmarks (avg over 10 runs)');
    print('═══════════════════════════════════════════════');
  });

  testWidgets('AppButton build benchmark', (tester) async {
    final avg = await measureBuildTime(
      tester,
      () => AppButton.primary(label: 'Sign In', onPressed: () {}),
    );
    print('  AppButton.primary  ........  ${avg.toStringAsFixed(1)} µs');
    // Reasonable threshold: should complete well under 100ms
    expect(avg, lessThan(100000));
  });

  testWidgets('AppCard build benchmark', (tester) async {
    final avg = await measureBuildTime(
      tester,
      () => const AppCard(child: Text('Card content')),
    );
    print('  AppCard  ..................  ${avg.toStringAsFixed(1)} µs');
    expect(avg, lessThan(100000));
  });

  testWidgets('AppTextField build benchmark', (tester) async {
    final avg = await measureBuildTime(
      tester,
      () => const AppTextField(labelText: 'Label', hintText: 'Hint'),
    );
    print('  AppTextField  .............  ${avg.toStringAsFixed(1)} µs');
    expect(avg, lessThan(100000));
  });

  testWidgets('EmptyState build benchmark', (tester) async {
    final avg = await measureBuildTime(
      tester,
      () => const EmptyState(
        icon: Icon(Icons.inbox_outlined),
        title: 'No data',
      ),
    );
    print('  EmptyState  ...............  ${avg.toStringAsFixed(1)} µs');
    expect(avg, lessThan(100000));
  });

  testWidgets('All widgets composite benchmark', (tester) async {
    // Measure building all widgets together in a single frame to simulate
    // a realistic screen composition.
    final stopwatch = Stopwatch()..start();

    await tester.pumpWidget(wrapInApp(
      SingleChildScrollView(
        child: Column(
          children: [
            AppButton.primary(label: 'Primary', onPressed: () {}),
            const SizedBox(height: 12),
            const AppCard(child: Text('Card')),
            const SizedBox(height: 12),
            const AppTextField(labelText: 'Field'),
            const SizedBox(height: 12),
            const EmptyState(
              icon: Icon(Icons.info_outline),
              title: 'Info',
            ),
          ],
        ),
      ),
    ));
    await tester.pumpAndSettle();
    stopwatch.stop();

    print('  Composite (all 4)  .......  ${stopwatch.elapsedMicroseconds} µs');
    expect(stopwatch.elapsedMicroseconds, lessThan(500000));
  });

  tearDownAll(() {
    print('═══════════════════════════════════════════════');
  });
}
