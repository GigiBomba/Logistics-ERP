import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/shared/widgets/transport_status_actions.dart';
import 'package:operion_mobile/shared/widgets/app_button.dart';

/// Helper to wrap a widget in [MaterialApp] for testing.
Widget wrapInApp(Widget child) {
  return MaterialApp(home: Scaffold(body: child));
}

void main() {
  // ==========================================================================
  // TransportStatusActions (static helpers)
  // ==========================================================================
  group('TransportStatusActions', () {
    group('getNextActions', () {
      test('planned returns one loading action', () {
        final actions = TransportStatusActions.getNextActions('planned');
        expect(actions, hasLength(1));
        expect(actions[0].status, 'loading');
        expect(actions[0].isPrimary, isTrue);
      });

      test('loading returns one in_transit action', () {
        final actions = TransportStatusActions.getNextActions('loading');
        expect(actions, hasLength(1));
        expect(actions[0].status, 'in_transit');
        expect(actions[0].isPrimary, isTrue);
      });

      test('in_transit returns delivered (primary) and overdue (secondary)',
          () {
        final actions = TransportStatusActions.getNextActions('in_transit');
        expect(actions, hasLength(2));
        expect(actions[0].status, 'delivered');
        expect(actions[0].isPrimary, isTrue);
        expect(actions[1].status, 'overdue');
        expect(actions[1].isPrimary, isFalse);
      });

      test('delivered returns empty list', () {
        expect(
          TransportStatusActions.getNextActions('delivered'),
          isEmpty,
        );
      });

      test('cancelled returns empty list', () {
        expect(
          TransportStatusActions.getNextActions('cancelled'),
          isEmpty,
        );
      });

      test('unknown status returns empty list', () {
        expect(
          TransportStatusActions.getNextActions('unknown'),
          isEmpty,
        );
      });
    });

    group('isTerminal', () {
      test('delivered is terminal', () {
        expect(TransportStatusActions.isTerminal('delivered'), isTrue);
      });

      test('cancelled is terminal', () {
        expect(TransportStatusActions.isTerminal('cancelled'), isTrue);
      });

      test('planned is not terminal', () {
        expect(TransportStatusActions.isTerminal('planned'), isFalse);
      });

      test('loading is not terminal', () {
        expect(TransportStatusActions.isTerminal('loading'), isFalse);
      });

      test('in_transit is not terminal', () {
        expect(TransportStatusActions.isTerminal('in_transit'), isFalse);
      });
    });
  });

  // ==========================================================================
  // TransportStatusButtons (widget)
  // ==========================================================================
  group('TransportStatusButtons', () {
    testWidgets('renders primary button for planned status', (tester) async {
      String? capturedStatus;
      await tester.pumpWidget(wrapInApp(
        TransportStatusButtons(
          currentStatus: 'planned',
          onStatusUpdate: (status) => capturedStatus = status,
        ),
      ));
      expect(find.text('Start Loading'), findsOneWidget);
      expect(find.byType(AppButton), findsOneWidget);
      expect(find.byType(ElevatedButton), findsOneWidget);

      // Tap triggers callback
      await tester.tap(find.text('Start Loading'));
      expect(capturedStatus, 'loading');
    });

    testWidgets('renders primary button for loading status', (tester) async {
      String? capturedStatus;
      await tester.pumpWidget(wrapInApp(
        TransportStatusButtons(
          currentStatus: 'loading',
          onStatusUpdate: (status) => capturedStatus = status,
        ),
      ));
      expect(find.text('Depart'), findsOneWidget);
      expect(find.byType(ElevatedButton), findsOneWidget);

      await tester.tap(find.text('Depart'));
      expect(capturedStatus, 'in_transit');
    });

    testWidgets('renders primary and secondary for in_transit status',
        (tester) async {
      String? capturedStatus;
      await tester.pumpWidget(wrapInApp(
        TransportStatusButtons(
          currentStatus: 'in_transit',
          onStatusUpdate: (status) => capturedStatus = status,
        ),
      ));
      // Primary: Mark Delivered
      expect(find.text('Mark Delivered'), findsOneWidget);
      expect(find.text('Report Delay'), findsOneWidget);
      // Two buttons
      expect(find.byType(AppButton), findsExactly(2));
      // First is ElevatedButton (primary), second is OutlinedButton (secondary)
      expect(find.byType(ElevatedButton), findsOneWidget);
      expect(find.byType(OutlinedButton), findsOneWidget);

      await tester.tap(find.text('Mark Delivered'));
      expect(capturedStatus, 'delivered');
    });

    testWidgets('renders nothing for terminal statuses', (tester) async {
      for (final status in ['delivered', 'cancelled']) {
        await tester.pumpWidget(wrapInApp(
          TransportStatusButtons(
            currentStatus: status,
            onStatusUpdate: (_) {},
          ),
        ));
        // Should render SizedBox.shrink — nothing visible
        expect(find.byType(SizedBox), findsOneWidget);
        expect(find.byType(AppButton), findsNothing);
        expect(find.byType(TransportStatusButtons), findsOneWidget);
      }
    });

    testWidgets('shows fallback text for unknown status', (tester) async {
      await tester.pumpWidget(wrapInApp(
        TransportStatusButtons(
          currentStatus: 'unknown',
          onStatusUpdate: (_) {},
        ),
      ));
      expect(
        find.text('No actions available for "unknown" status.'),
        findsOneWidget,
      );
      expect(find.byType(AppButton), findsNothing);
    });

    testWidgets('shows custom noActionsText when provided', (tester) async {
      await tester.pumpWidget(wrapInApp(
        TransportStatusButtons(
          currentStatus: 'unknown',
          onStatusUpdate: (_) {},
          noActionsText: 'No transitions available',
        ),
      ));
      expect(find.text('No transitions available'), findsOneWidget);
      expect(find.text('No actions available for'), findsNothing);
    });

    testWidgets('labelResolver overrides action labels', (tester) async {
      await tester.pumpWidget(wrapInApp(
        TransportStatusButtons(
          currentStatus: 'planned',
          onStatusUpdate: (_) {},
          labelResolver: (status) => status == 'loading'
              ? 'Start Loading Custom'
              : status,
        ),
      ));
      expect(find.text('Start Loading Custom'), findsOneWidget);
      expect(find.text('Start Loading'), findsNothing);
    });

    testWidgets('loadingStatuses shows CircularProgressIndicator',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        TransportStatusButtons(
          currentStatus: 'planned',
          onStatusUpdate: (_) {},
          loadingStatuses: {'loading'},
        ),
      ));
      // The button should be in loading state
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      // Label should not be visible when loading
      expect(find.text('Start Loading'), findsNothing);
    });

    testWidgets('loading button is disabled', (tester) async {
      await tester.pumpWidget(wrapInApp(
        TransportStatusButtons(
          currentStatus: 'planned',
          onStatusUpdate: (_) {},
          loadingStatuses: {'loading'},
        ),
      ));
      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(button.onPressed, isNull);
    });

    testWidgets('loadingStatuses does not affect other actions', (tester) async {
      await tester.pumpWidget(wrapInApp(
        TransportStatusButtons(
          currentStatus: 'in_transit',
          onStatusUpdate: (_) {},
          // Only mark one action as loading
          loadingStatuses: {'delivered'},
        ),
      ));
      // Delivered button should be loading
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      // Overdue should still have its label visible and be tappable
      expect(find.text('Report Delay'), findsOneWidget);
    });

    testWidgets('isOffline parameter is accepted without effect', (tester) async {
      // isOffline is declared but not used in the current build method.
      // Verify it doesn't crash when set to true.
      await tester.pumpWidget(wrapInApp(
        TransportStatusButtons(
          currentStatus: 'planned',
          isOffline: true,
          onStatusUpdate: (_) {},
        ),
      ));
      expect(find.text('Start Loading'), findsOneWidget);
    });

    testWidgets('secondary button tap triggers callback for in_transit',
        (tester) async {
      String? capturedStatus;
      await tester.pumpWidget(wrapInApp(
        TransportStatusButtons(
          currentStatus: 'in_transit',
          onStatusUpdate: (status) => capturedStatus = status,
        ),
      ));
      await tester.tap(find.text('Report Delay'));
      expect(capturedStatus, 'overdue');
    });

    testWidgets('multiple pumpAndSettle calls are stable', (tester) async {
      await tester.pumpWidget(wrapInApp(
        TransportStatusButtons(
          currentStatus: 'in_transit',
          onStatusUpdate: (_) {},
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Mark Delivered'), findsOneWidget);
      expect(find.text('Report Delay'), findsOneWidget);
    });
  });
}
