import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/copilot_endpoints.dart';
import 'package:operion_mobile/features/copilot/providers/copilot_providers.dart';
import 'package:operion_mobile/features/copilot/screens/copilot_screen.dart';
import 'package:operion_mobile/features/copilot/models/copilot_models.dart';
import 'package:operion_mobile/l10n/app_localizations.dart';

// ── Fake dependencies ─────────────────────────────────────────────────────

class _FakeEndpoints extends CopilotEndpoints {
  _FakeEndpoints()
      : super(ApiClient.create(
          baseUrl: 'https://test.com',
          getAccessToken: () async => null,
        ));
}

/// A controllable fake that extends CopilotStateNotifier but overrides
/// only the sendMessage/confirmPlan/cancelPlan to be synchronous no-ops.
class _FakeCopilotStateNotifier extends CopilotStateNotifier {
  _FakeCopilotStateNotifier() : super(_FakeEndpoints());

  /// Exposed so tests can mutate state and pump.
  void setStateManually(CopilotMobileState newState) {
    state = newState;
  }

  bool sendMessageCalled = false;
  bool confirmPlanCalled = false;
  bool cancelPlanCalled = false;
  String? lastConfirmationPhrase;
  String? lastMessage;
  bool resetCalled = false;

  @override
  Future<void> sendMessage(String utterance) async {
    sendMessageCalled = true;
    lastMessage = utterance;
  }

  @override
  Future<void> confirmPlan({String? confirmationPhrase}) async {
    confirmPlanCalled = true;
    lastConfirmationPhrase = confirmationPhrase;
  }

  @override
  Future<void> cancelPlan() async {
    cancelPlanCalled = true;
  }

  @override
  void reset() {
    resetCalled = true;
    state = const CopilotIdle();
  }
}

// ── Test helpers ──────────────────────────────────────────────────────────

/// Wraps the screen in ProviderScope and MaterialApp with localizations.
Widget wrapScreen({
  _FakeCopilotStateNotifier? notifier,
  CopilotMobileState? initialState,
}) {
  final stateNotifier = notifier ?? _FakeCopilotStateNotifier();
  if (initialState != null) {
    stateNotifier.setStateManually(initialState);
  }

  return ProviderScope(
    overrides: [
      copilotStateProvider.overrideWith(
        (ref) => stateNotifier,
      ),
    ],
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const CopilotScreen(),
    ),
  );
}

CopilotExecutionPlan _testPlan({
  bool requiresConfirmation = false,
  List<int> levels = const [],
  String? phrase,
}) {
  return CopilotExecutionPlan(
    planId: 'plan-test',
    conversationId: 'conv-test',
    intent: const CopilotIntent(name: 'vehicle.search', rawUtterance: 'test'),
    requiresConfirmation: requiresConfirmation,
    confirmationPhrase: phrase,
    steps: levels.asMap().entries.map((e) => CopilotExecutionStep(
          stepId: 's${e.key}',
          toolName: 'vehicle.search',
          confirmationLevel: e.value,
          status: 'pending',
        )).toList(),
  );
}

void main() {
  // ==========================================================================
  // Initial state / empty state
  // ==========================================================================
  group('CopilotScreen — empty state', () {
    testWidgets('renders app bar with title', (tester) async {
      await tester.pumpWidget(wrapScreen());
      await tester.pumpAndSettle();

      expect(find.text('AI Co-Pilot'), findsOneWidget);
    });

    testWidgets('renders empty state message and prompt', (tester) async {
      await tester.pumpWidget(wrapScreen());
      await tester.pumpAndSettle();

      expect(find.text('Ask me anything about your fleet'), findsOneWidget);
      expect(find.text('Try: "Show my available trucks"'), findsOneWidget);
    });

    testWidgets('renders auto_awesome icon in empty state', (tester) async {
      await tester.pumpWidget(wrapScreen());
      await tester.pumpAndSettle();

      // There should be at least one auto_awesome icon
      expect(find.byIcon(Icons.auto_awesome), findsWidgets);
    });

    testWidgets('renders text input and send button', (tester) async {
      await tester.pumpWidget(wrapScreen());
      await tester.pumpAndSettle();

      expect(find.byType(TextField), findsOneWidget);
      expect(find.byIcon(Icons.send), findsOneWidget);
    });

    testWidgets('shows placeholder text in input', (tester) async {
      await tester.pumpWidget(wrapScreen());
      await tester.pumpAndSettle();

      expect(find.text('Type a command or question...'), findsOneWidget);
    });

    testWidgets('renders new conversation button', (tester) async {
      await tester.pumpWidget(wrapScreen());
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.refresh), findsOneWidget);
    });
  });

  // ==========================================================================
  // Processing state
  // ==========================================================================
  group('CopilotScreen — processing state', () {
    testWidgets('shows loading indicator when processing', (tester) async {
      await tester.pumpWidget(wrapScreen(
        initialState: const CopilotProcessing(),
      ));
      await tester.pump();

      // Loading indicator in center of empty state
      expect(find.byType(CircularProgressIndicator), findsWidgets);
    });

    testWidgets('disables send button when processing', (tester) async {
      await tester.pumpWidget(wrapScreen(
        initialState: const CopilotProcessing(),
      ));
      await tester.pump();

      // The send button should be replaced by a progress indicator
      // when isLoading is true
      expect(find.byIcon(Icons.send), findsNothing);
    });

    testWidgets('disables text field when processing', (tester) async {
      final notifier = _FakeCopilotStateNotifier();
      await tester.pumpWidget(wrapScreen(
        notifier: notifier,
        initialState: const CopilotProcessing(),
      ));
      await tester.pump();

      final textField = tester.widget<TextField>(find.byType(TextField));
      expect(textField.enabled, false);
    });
  });

  // ==========================================================================
  // Sending messages
  // ==========================================================================
  group('CopilotScreen — sending messages', () {
    testWidgets('sending a message calls sendMessage on notifier',
        (tester) async {
      final notifier = _FakeCopilotStateNotifier();
      await tester.pumpWidget(wrapScreen(notifier: notifier));
      await tester.pumpAndSettle();

      // Type a message
      await tester.enterText(find.byType(TextField), 'find trucks');
      await tester.pumpAndSettle();

      // Tap send button
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      expect(notifier.sendMessageCalled, true);
      expect(notifier.lastMessage, 'find trucks');
    });

    testWidgets('sending empty message does not call notifier', (tester) async {
      final notifier = _FakeCopilotStateNotifier();
      await tester.pumpWidget(wrapScreen(notifier: notifier));
      await tester.pumpAndSettle();

      // Tap send with empty input
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      expect(notifier.sendMessageCalled, false);
    });

    testWidgets('text field clears after sending message', (tester) async {
      final notifier = _FakeCopilotStateNotifier();
      await tester.pumpWidget(wrapScreen(notifier: notifier));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'find trucks');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // Text field should be cleared
      final textField = tester.widget<TextField>(find.byType(TextField));
      expect(textField.controller!.text, isEmpty);
    });

    testWidgets('sending via onSubmitted calls notifier', (tester) async {
      final notifier = _FakeCopilotStateNotifier();
      await tester.pumpWidget(wrapScreen(notifier: notifier));
      await tester.pumpAndSettle();

      // Type and submit
      await tester.enterText(find.byType(TextField), 'search');
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pumpAndSettle();

      expect(notifier.sendMessageCalled, true);
    });
  });

  // ==========================================================================
  // Awaiting confirmation state
  // ==========================================================================
  group('CopilotScreen — confirmation state', () {
    testWidgets('shows confirmation bar when awaiting confirmation',
        (tester) async {
      final plan = _testPlan(
        requiresConfirmation: true,
        levels: [2],
      );
      await tester.pumpWidget(wrapScreen(
        initialState: CopilotAwaitingConfirmation(plan: plan),
      ));
      await tester.pumpAndSettle();

      // Should show the confirmation text
      expect(find.text('Operion AI suggests the following action:'), findsOneWidget);
    });

    testWidgets('shows Level 3 confirmation bar with phrase input',
        (tester) async {
      final plan = _testPlan(
        requiresConfirmation: true,
        levels: [3],
        phrase: 'confirm',
      );
      await tester.pumpWidget(wrapScreen(
        initialState: CopilotAwaitingConfirmation(plan: plan),
      ));
      await tester.pumpAndSettle();

      // Should show Level 3 title
      expect(
        find.text('Level 3 — Type confirmation to proceed'),
        findsOneWidget,
      );
    });

    testWidgets('tapping confirm calls confirmPlan', (tester) async {
      final notifier = _FakeCopilotStateNotifier();
      final plan = _testPlan(
        requiresConfirmation: true,
        levels: [1],
      );
      await tester.pumpWidget(wrapScreen(
        notifier: notifier,
        initialState: CopilotAwaitingConfirmation(plan: plan),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Confirm'));
      await tester.pumpAndSettle();

      expect(notifier.confirmPlanCalled, true);
    });

    testWidgets('tapping cancel calls cancelPlan', (tester) async {
      final notifier = _FakeCopilotStateNotifier();
      final plan = _testPlan(
        requiresConfirmation: true,
        levels: [1],
      );
      await tester.pumpWidget(wrapScreen(
        notifier: notifier,
        initialState: CopilotAwaitingConfirmation(plan: plan),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(notifier.cancelPlanCalled, true);
    });
  });

  // ==========================================================================
  // Awaiting clarification state
  // ==========================================================================
  group('CopilotScreen — clarification state', () {
    testWidgets('shows clarification bar when awaiting clarification',
        (tester) async {
      await tester.pumpWidget(wrapScreen(
        initialState: const CopilotAwaitingClarification(
          questionKey: 'copilot.clarification.missing_entities',
        ),
      ));
      await tester.pumpAndSettle();

      expect(
        find.text('copilot.clarification.missing_entities'),
        findsOneWidget,
      );
    });

    testWidgets('shows clarification input and send button', (tester) async {
      await tester.pumpWidget(wrapScreen(
        initialState: const CopilotAwaitingClarification(
          questionKey: 'copilot.clarification.test',
        ),
      ));
      await tester.pumpAndSettle();

      // Should have the clarification text field and send icon
      expect(find.byIcon(Icons.send), findsWidgets); // one in input bar, one for clarification
    });
  });

  // ==========================================================================
  // New conversation / reset
  // ==========================================================================
  group('CopilotScreen — new conversation', () {
    testWidgets('tapping refresh calls reset on notifier', (tester) async {
      final notifier = _FakeCopilotStateNotifier();
      await tester.pumpWidget(wrapScreen(notifier: notifier));
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.refresh));
      await tester.pumpAndSettle();

      expect(notifier.resetCalled, true);
    });
  });

  // ==========================================================================
  // Error state
  // ==========================================================================
  group('CopilotScreen — error state', () {
    testWidgets('adds error message to chat when error occurs', (tester) async {
      final notifier = _FakeCopilotStateNotifier();

      // Start idle, then trigger an error
      await tester.pumpWidget(wrapScreen(notifier: notifier));
      await tester.pumpAndSettle();

      // Trigger error state - this should add an error message via listener
      notifier.setStateManually(const CopilotError(messageKey: 'copilot.error.unexpected'));
      await tester.pumpAndSettle();

      // Should show the error message in the chat
      expect(find.text('copilot.error.unexpected'), findsOneWidget);
    });
  });

  // ==========================================================================
  // Completed state
  // ==========================================================================
  group('CopilotScreen — completed state', () {
    testWidgets('adds summary message when completed with summaryKey',
        (tester) async {
      final notifier = _FakeCopilotStateNotifier();

      await tester.pumpWidget(wrapScreen(notifier: notifier));
      await tester.pumpAndSettle();

      // Trigger completed with summary
      notifier.setStateManually(const CopilotCompleted(
        summaryKey: 'copilot.summary.done',
      ));
      await tester.pumpAndSettle();

      expect(find.text('copilot.summary.done'), findsOneWidget);
    });
  });
}
