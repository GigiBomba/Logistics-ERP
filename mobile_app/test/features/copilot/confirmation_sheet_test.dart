import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/features/copilot/models/copilot_models.dart';
import 'package:operion_mobile/features/copilot/widgets/copilot_confirmation_sheet.dart';
import 'package:operion_mobile/l10n/app_localizations.dart';

/// Helper: wraps [child] in [MaterialApp] with localization support.
Widget wrapSheet(Widget child) {
  return MaterialApp(
    localizationsDelegates: const [
      AppLocalizations.delegate,
      DefaultMaterialLocalizations.delegate,
      DefaultWidgetsLocalizations.delegate,
    ],
    supportedLocales: AppLocalizations.supportedLocales,
    home: Scaffold(body: child),
  );
}

/// Helper: creates a [CopilotExecutionPlan] with the given step levels.
CopilotExecutionPlan _plan({
  required List<int> stepLevels,
  bool requiresConfirmation = true,
  String? confirmationPhrase,
}) {
  return CopilotExecutionPlan(
    planId: 'plan-1',
    conversationId: 'conv-1',
    intent: const CopilotIntent(name: 'vehicle.search', rawUtterance: 'test'),
    requiresConfirmation: requiresConfirmation,
    confirmationPhrase: confirmationPhrase,
    steps: stepLevels.asMap().entries.map((e) => CopilotExecutionStep(
          stepId: 's${e.key}',
          toolName: e.value >= 3 ? 'dispatch.create' : 'vehicle.search',
          confirmationLevel: e.value,
          parameters: e.value >= 3 ? {'action': 'delete'} : {},
          status: 'pending',
        )).toList(),
  );
}

void main() {
  group('CopilotConfirmationSheet', () {
    // ======================================================================
    // Basic rendering
    // ======================================================================
    group('basic rendering', () {
      testWidgets('renders title and handle', (tester) async {
        final plan = _plan(stepLevels: [1]);
        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () {},
            onCancel: () {},
          ),
        ));
        await tester.pumpAndSettle();

        // Title should be present (localized)
        expect(find.text('Confirm Action'), findsOneWidget);
      });

      testWidgets('renders step cards for each step', (tester) async {
        final plan = _plan(stepLevels: [1, 2]);
        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () {},
            onCancel: () {},
          ),
        ));
        await tester.pumpAndSettle();

        // Should show step tool names
        expect(find.text('vehicle.search'), findsNWidgets(2));
      });

      testWidgets('renders cancel and confirm buttons', (tester) async {
        final plan = _plan(stepLevels: [1]);
        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () {},
            onCancel: () {},
          ),
        ));
        await tester.pumpAndSettle();

        expect(find.text('Cancel'), findsOneWidget);
        expect(find.text('Confirm'), findsOneWidget);
      });

      testWidgets('confirm button is enabled for non-Level 3 plans',
          (tester) async {
        final plan = _plan(stepLevels: [1, 2]);
        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () {},
            onCancel: () {},
          ),
        ));
        await tester.pumpAndSettle();

        final confirmButton =
            tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Confirm'));
        expect(confirmButton.onPressed, isNotNull);
      });
    });

    // ======================================================================
    // Level 3 — destructive actions
    // ======================================================================
    group('Level 3 destructive actions', () {
      testWidgets('shows warning and phrase input for Level 3', (tester) async {
        final plan = _plan(
          stepLevels: [3],
          confirmationPhrase: 'I understand the risks',
        );
        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () {},
            onCancel: () {},
          ),
        ));
        await tester.pumpAndSettle();

        // Warning text should be visible
        expect(
          find.text('This action is IRREVERSIBLE. Type the confirmation phrase to continue.'),
          findsOneWidget,
        );

        // Phrase input should be present
        expect(find.byType(TextField), findsOneWidget);
      });

      testWidgets('confirm button is disabled when phrase is empty',
          (tester) async {
        final plan = _plan(
          stepLevels: [3],
          confirmationPhrase: 'I understand the risks',
        );
        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () {},
            onCancel: () {},
          ),
        ));
        await tester.pumpAndSettle();

        final confirmButton =
            tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Confirm'));
        expect(confirmButton.onPressed, isNull);
      });

      testWidgets('confirm button enables when phrase matches', (tester) async {
        final plan = _plan(
          stepLevels: [3],
          confirmationPhrase: 'I understand the risks',
        );
        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () {},
            onCancel: () {},
          ),
        ));
        await tester.pumpAndSettle();

        // Type the matching phrase
        await tester.enterText(find.byType(TextField), 'I understand the risks');
        await tester.pumpAndSettle();

        final confirmButton =
            tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Confirm'));
        expect(confirmButton.onPressed, isNotNull);
      });

      testWidgets('confirm button stays disabled with wrong phrase',
          (tester) async {
        final plan = _plan(
          stepLevels: [3],
          confirmationPhrase: 'I understand the risks',
        );
        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () {},
            onCancel: () {},
          ),
        ));
        await tester.pumpAndSettle();

        // Type a wrong phrase
        await tester.enterText(find.byType(TextField), 'wrong phrase');
        await tester.pumpAndSettle();

        final confirmButton =
            tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Confirm'));
        expect(confirmButton.onPressed, isNull);
      });

      testWidgets('trims whitespace when matching phrase', (tester) async {
        final plan = _plan(
          stepLevels: [3],
          confirmationPhrase: 'confirm',
        );
        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () {},
            onCancel: () {},
          ),
        ));
        await tester.pumpAndSettle();

        // Type with leading/trailing spaces
        await tester.enterText(find.byType(TextField), '  confirm  ');
        await tester.pumpAndSettle();

        final confirmButton =
            tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'Confirm'));
        expect(confirmButton.onPressed, isNotNull);
      });
    });

    // ======================================================================
    // Mixed level steps
    // ======================================================================
    group('mixed level steps', () {
      testWidgets('shows Level 3 warning when any step has level >= 3',
          (tester) async {
        final plan = _plan(
          stepLevels: [1, 3],
          confirmationPhrase: 'proceed',
        );
        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () {},
            onCancel: () {},
          ),
        ));
        await tester.pumpAndSettle();

        // Warning should appear since one step is Level 3
        expect(
          find.textContaining('IRREVERSIBLE'),
          findsOneWidget,
        );
      });

      testWidgets('shows info and warning icons for different levels',
          (tester) async {
        final plan = _plan(stepLevels: [1, 3]);
        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () {},
            onCancel: () {},
          ),
        ));
        await tester.pumpAndSettle();

        // Level 1 step should have info icon
        // Level 3 step should have warning icon
        expect(find.byIcon(Icons.info_outline), findsOneWidget);
        expect(find.byIcon(Icons.warning_rounded), findsOneWidget);
      });
    });

    // ======================================================================
    // Actions
    // ======================================================================
    group('actions', () {
      testWidgets('tapping Cancel calls onCancel', (tester) async {
        bool cancelled = false;
        final plan = _plan(stepLevels: [1]);

        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () {},
            onCancel: () => cancelled = true,
          ),
        ));
        await tester.pumpAndSettle();

        await tester.tap(find.text('Cancel'));
        expect(cancelled, true);
      });

      testWidgets('tapping Confirm for non-Level 3 calls onConfirm',
          (tester) async {
        bool confirmed = false;
        final plan = _plan(stepLevels: [1, 2]);

        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () => confirmed = true,
            onCancel: () {},
          ),
        ));
        await tester.pumpAndSettle();

        await tester.tap(find.text('Confirm'));
        expect(confirmed, true);
      });

      testWidgets('tapping Confirm for Level 3 with matching phrase calls onConfirm',
          (tester) async {
        bool confirmed = false;
        final plan = _plan(
          stepLevels: [3],
          confirmationPhrase: 'yes',
        );

        await tester.pumpWidget(wrapSheet(
          CopilotConfirmationSheet(
            plan: plan,
            onConfirm: () => confirmed = true,
            onCancel: () {},
          ),
        ));
        await tester.pumpAndSettle();

        // Type matching phrase
        await tester.enterText(find.byType(TextField), 'yes');
        await tester.pumpAndSettle();

        await tester.tap(find.text('Confirm'));
        expect(confirmed, true);
      });
    });
  });
}
