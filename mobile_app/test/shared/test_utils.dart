import 'package:flutter_test/flutter_test.dart';

/// Bounded [WidgetTester.pumpAndSettle] helper.
///
/// Steps the fake clock in 100ms increments (like the bare
/// `pumpAndSettle()`) but caps the fake-time budget at 5 seconds instead of
/// the default 10 minutes. This converts a perpetual-animation failure from a
/// 10-minute fake-clock spin into a fast, bounded `pumpAndSettle timed out`
/// failure while remaining behavior-identical for tests that settle quickly.
Future<void> settle(WidgetTester tester) => tester.pumpAndSettle(
      const Duration(milliseconds: 100),
      EnginePhase.sendSemanticsUpdate,
      const Duration(seconds: 5),
    );