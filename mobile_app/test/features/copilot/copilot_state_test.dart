import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/copilot_endpoints.dart';
import 'package:operion_mobile/features/copilot/models/copilot_models.dart';
import 'package:operion_mobile/features/copilot/providers/copilot_providers.dart';

// ── Fake endpoints for notifier tests ─────────────────────────────────────

class _FakeCopilotEndpoints extends CopilotEndpoints {
  _FakeCopilotEndpoints()
      : super(ApiClient.create(
          baseUrl: 'https://test.com',
          getAccessToken: () async => null,
        ));

  CopilotResponse Function()? onChat;
  Map<String, dynamic> Function()? onConfirmPlan;
  Map<String, dynamic> Function()? onCancelPlan;

  @override
  Future<CopilotResponse> chat({
    required String utterance,
    String? conversationId,
    String language = 'en',
    CancelToken? cancelToken,
  }) async {
    return onChat?.call() ??
        CopilotResponse(conversationId: 'test-conv');
  }

  @override
  Future<Map<String, dynamic>> confirmPlan(
    String planId,
    CancelToken? cancelToken, {
    String? confirmationPhrase,
  }) async {
    return onConfirmPlan?.call() ?? {'status': 'completed'};
  }

  @override
  Future<Map<String, dynamic>> cancelPlan(String planId) async {
    return onCancelPlan?.call() ?? {'status': 'cancelled'};
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────

CopilotExecutionPlan _planWithConfirmationLevels({
  List<int> levels = const [],
  bool requiresConfirmation = true,
  String? confirmationPhrase,
}) {
  return CopilotExecutionPlan(
    planId: 'plan-test',
    conversationId: 'conv-test',
    intent: const CopilotIntent(name: 'vehicle.search', rawUtterance: 'test'),
    requiresConfirmation: requiresConfirmation,
    confirmationPhrase: confirmationPhrase,
    steps: levels.asMap().entries.map((e) => CopilotExecutionStep(
          stepId: 's${e.key}',
          toolName: 'vehicle.search',
          confirmationLevel: e.value,
          status: 'pending',
        )).toList(),
  );
}

void main() {
  group('CopilotExecutionStep', () {
    test('fromJson parses a running step correctly', () {
      final json = {
        'step_id': 's1',
        'tool_name': 'vehicle.search',
        'status': 'running',
        'tool_version': '1.0.0',
        'parameters': <String, dynamic>{},
        'depends_on': <dynamic>[],
        'confirmation_level': 0,
      };
      final step = CopilotExecutionStep.fromJson(json);
      expect(step.stepId, 's1');
      expect(step.toolName, 'vehicle.search');
      expect(step.status, 'running');
      expect(step.isTerminal, false);
    });

    test('fromJson parses a succeeded step correctly', () {
      final json = {
        'step_id': 's2',
        'tool_name': 'vehicle.search',
        'status': 'succeeded',
        'result': {'vehicles': <dynamic>[]},
      };
      final step = CopilotExecutionStep.fromJson(json);
      expect(step.status, 'succeeded');
      expect(step.isTerminal, true);
      expect(step.result, isNotNull);
    });

    test('fromJson handles failed step with error', () {
      final json = {
        'step_id': 's3',
        'tool_name': 'dispatch.create',
        'status': 'failed',
        'error': 'Vehicle not available',
      };
      final step = CopilotExecutionStep.fromJson(json);
      expect(step.status, 'failed');
      expect(step.error, 'Vehicle not available');
      expect(step.isTerminal, true);
    });

    test('fromJson handles missing fields with defaults', () {
      final json = <String, dynamic>{};
      final step = CopilotExecutionStep.fromJson(json);
      expect(step.stepId, '');
      expect(step.toolName, '');
      expect(step.status, 'pending');
      expect(step.isTerminal, false);
    });
  });

  group('CopilotExecutionPlan', () {
    test('fromJson parses plan with confirmation', () {
      final json = {
        'plan_id': 'plan-123',
        'conversation_id': 'conv-456',
        'intent': {'name': 'dispatch.create', 'raw_utterance': 'test'},
        'requires_confirmation': true,
        'steps': [
          {
            'step_id': 's1',
            'tool_name': 'dispatch.create',
            'confirmation_level': 2,
            'status': 'pending',
          }
        ],
      };
      final plan = CopilotExecutionPlan.fromJson(json);
      expect(plan.planId, 'plan-123');
      expect(plan.requiresConfirmation, true);
      expect(plan.steps.length, 1);
      expect(plan.steps.first.toolName, 'dispatch.create');
    });

    test('fromJson handles empty response', () {
      final json = <String, dynamic>{};
      final plan = CopilotExecutionPlan.fromJson(json);
      expect(plan.planId, '');
      expect(plan.requiresConfirmation, false);
      expect(plan.steps, isEmpty);
    });

    group('isLevel3', () {
      test('returns false when all steps are below Level 3', () {
        final plan = _planWithConfirmationLevels(levels: [0, 1, 2]);
        expect(plan.isLevel3, false);
      });

      test('returns true when any step has Level 3', () {
        final plan = _planWithConfirmationLevels(levels: [0, 3]);
        expect(plan.isLevel3, true);
      });

      test('returns true when any step has Level 4+', () {
        final plan = _planWithConfirmationLevels(levels: [1, 4]);
        expect(plan.isLevel3, true);
      });
    });

    group('maxConfirmationLevel', () {
      test('returns 0 when there are no steps', () {
        final plan = _planWithConfirmationLevels(levels: []);
        expect(plan.maxConfirmationLevel, 0);
      });

      test('returns the highest confirmation level across steps', () {
        final plan = _planWithConfirmationLevels(levels: [0, 2, 1]);
        expect(plan.maxConfirmationLevel, 2);
      });

      test('returns 3 when a step has Level 3', () {
        final plan = _planWithConfirmationLevels(levels: [1, 3, 2]);
        expect(plan.maxConfirmationLevel, 3);
      });
    });
  });

  group('CopilotAwaitingConfirmation', () {
    test('isLevel3 reflects plan level when true', () {
      final plan = _planWithConfirmationLevels(levels: [0, 3]);
      final state = CopilotAwaitingConfirmation(plan: plan);
      expect(state.plan.isLevel3, true);
      expect(state.plan.maxConfirmationLevel, 3);
    });

    test('isLevel3 reflects plan level when false', () {
      final plan = _planWithConfirmationLevels(levels: [0, 1, 2]);
      final state = CopilotAwaitingConfirmation(plan: plan);
      expect(state.plan.isLevel3, false);
      expect(state.plan.maxConfirmationLevel, 2);
    });

    test('stores the confirmation phrase from the plan', () {
      final plan = _planWithConfirmationLevels(
        levels: [3],
        confirmationPhrase: 'I understand the risks',
      );
      final state = CopilotAwaitingConfirmation(plan: plan);
      expect(state.plan.confirmationPhrase, 'I understand the risks');
    });
  });

  group('CopilotResponse', () {
    test('fromJson parses clarification response', () {
      final json = {
        'conversation_id': 'conv-789',
        'clarification_question_key': 'copilot.clarification.missing_entities',
      };
      final resp = CopilotResponse.fromJson(json);
      expect(resp.conversationId, 'conv-789');
      expect(resp.clarificationQuestionKey,
          'copilot.clarification.missing_entities');
      expect(resp.plan, isNull);
    });

    test('fromJson parses plan response', () {
      final json = {
        'conversation_id': 'conv-101',
        'plan': {
          'plan_id': 'plan-202',
          'conversation_id': 'conv-101',
          'intent': {'name': 'vehicle.search', 'raw_utterance': 'find trucks'},
          'requires_confirmation': false,
        },
      };
      final resp = CopilotResponse.fromJson(json);
      expect(resp.plan, isNotNull);
      expect(resp.plan!.intent.name, 'vehicle.search');
    });
  });

  group('CopilotStateNotifier', () {
    late _FakeCopilotEndpoints fakeEndpoints;
    late CopilotStateNotifier notifier;

    setUp(() {
      fakeEndpoints = _FakeCopilotEndpoints();
      notifier = CopilotStateNotifier(fakeEndpoints);
    });

    tearDown(() {
      notifier.dispose();
    });

    group('initial state', () {
      test('starts in CopilotIdle', () {
        expect(notifier.state, isA<CopilotIdle>());
      });

      test('conversationId is null initially', () {
        expect(notifier.conversationId, isNull);
      });
    });

    group('sendMessage', () {
      test('transitions to CopilotProcessing then CopilotCompleted on success',
          () async {
        fakeEndpoints.onChat = () => const CopilotResponse(
              conversationId: 'conv-1',
              summaryKey: 'copilot.summary.done',
            );

        // Initial state
        expect(notifier.state, isA<CopilotIdle>());

        await notifier.sendMessage('find trucks');

        // After processing, should be completed
        final finalState = notifier.state;
        expect(finalState, isA<CopilotCompleted>());
        expect((finalState as CopilotCompleted).summaryKey,
            'copilot.summary.done');
      });

      test('transitions to CopilotAwaitingClarification when backend asks',
          () async {
        fakeEndpoints.onChat = () => const CopilotResponse(
              conversationId: 'conv-2',
              clarificationQuestionKey:
                  'copilot.clarification.missing_entities',
            );

        await notifier.sendMessage('find trucks');

        final state = notifier.state;
        expect(state, isA<CopilotAwaitingClarification>());
        expect((state as CopilotAwaitingClarification).questionKey,
            'copilot.clarification.missing_entities');
      });

      test('transitions to CopilotAwaitingConfirmation when plan requires it',
          () async {
        final plan = _planWithConfirmationLevels(
          levels: [2],
          requiresConfirmation: true,
        );
        fakeEndpoints.onChat = () => CopilotResponse(
              conversationId: 'conv-3',
              plan: plan,
            );

        await notifier.sendMessage('confirm dispatch');

        final state = notifier.state;
        expect(state, isA<CopilotAwaitingConfirmation>());
        expect((state as CopilotAwaitingConfirmation).plan.planId, 'plan-test');
      });

      test('ignores empty utterance', () async {
        // No onChat override — calling with empty should not trigger anything
        await notifier.sendMessage('   ');
        expect(notifier.state, isA<CopilotIdle>());
      });

      test('transitions to CopilotError on endpoint failure', () async {
        fakeEndpoints.onChat = () => throw Exception('network error');

        await notifier.sendMessage('find trucks');

        expect(notifier.state, isA<CopilotError>());
        expect((notifier.state as CopilotError).messageKey,
            'copilot.error.unexpected');
      });
    });

    group('confirmPlan', () {
      test('with confirmationPhrase transitions to CopilotExecuting then CopilotCompleted',
          () async {
        // Arrange: put notifier in AwaitingConfirmation state
        final plan = _planWithConfirmationLevels(
          levels: [3],
          confirmationPhrase: 'I understand',
        );
        notifier.sendMessage(''); // no-op, won't change state
        // Force state to CopilotAwaitingConfirmation
        notifier = CopilotStateNotifier(fakeEndpoints)
          ..state = CopilotAwaitingConfirmation(plan: plan);

        fakeEndpoints.onConfirmPlan = () => {'status': 'completed'};

        await notifier.confirmPlan(confirmationPhrase: 'I understand');

        final finalState = notifier.state;
        expect(finalState, isA<CopilotCompleted>());
        expect((finalState as CopilotCompleted).summaryKey,
            'copilot.summary.confirmed');
      });

      test('without confirmationPhrase for non-Level 3 plan', () async {
        final plan = _planWithConfirmationLevels(levels: [2]);
        notifier = CopilotStateNotifier(fakeEndpoints)
          ..state = CopilotAwaitingConfirmation(plan: plan);

        fakeEndpoints.onConfirmPlan = () => {'status': 'completed'};

        await notifier.confirmPlan();

        expect(notifier.state, isA<CopilotCompleted>());
      });

      test('does nothing when not in CopilotAwaitingConfirmation', () async {
        // State is Idle (default)
        await notifier.confirmPlan(confirmationPhrase: 'phrase');

        // State unchanged
        expect(notifier.state, isA<CopilotIdle>());
      });

      test('transitions to CopilotError on endpoint failure', () async {
        final plan = _planWithConfirmationLevels(levels: [3]);
        notifier = CopilotStateNotifier(fakeEndpoints)
          ..state = CopilotAwaitingConfirmation(plan: plan);

        fakeEndpoints.onConfirmPlan = () => throw Exception('API error');

        await notifier.confirmPlan(confirmationPhrase: 'phrase');

        expect(notifier.state, isA<CopilotError>());
      });
    });

    group('cancelPlan', () {
      test('transitions to CopilotIdle on success', () async {
        final plan = _planWithConfirmationLevels(levels: [2]);
        notifier = CopilotStateNotifier(fakeEndpoints)
          ..state = CopilotAwaitingConfirmation(plan: plan);

        await notifier.cancelPlan();

        expect(notifier.state, isA<CopilotIdle>());
      });

      test('does nothing when not in CopilotAwaitingConfirmation', () async {
        await notifier.cancelPlan();

        expect(notifier.state, isA<CopilotIdle>());
      });

      test('transitions to CopilotError on endpoint failure', () async {
        final plan = _planWithConfirmationLevels(levels: [2]);
        notifier = CopilotStateNotifier(fakeEndpoints)
          ..state = CopilotAwaitingConfirmation(plan: plan);

        fakeEndpoints.onCancelPlan = () => throw Exception('API error');

        await notifier.cancelPlan();

        expect(notifier.state, isA<CopilotError>());
      });
    });

    group('reset', () {
      test('returns to CopilotIdle and clears conversationId', () async {
        // Put notifier into a non-idle state
        final plan = _planWithConfirmationLevels(levels: [2]);
        notifier = CopilotStateNotifier(fakeEndpoints)
          ..state = CopilotAwaitingConfirmation(plan: plan);

        notifier.reset();

        expect(notifier.state, isA<CopilotIdle>());
        expect(notifier.conversationId, isNull);
      });
    });
  });
}
