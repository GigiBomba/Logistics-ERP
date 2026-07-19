import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
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

// ── Provider chain helpers ────────────────────────────────────────────────

/// Creates a [ProviderContainer] with overridden copilotEndpointsProvider.
ProviderContainer _createContainer({
  CopilotEndpoints? endpoints,
}) {
  final container = ProviderContainer(
    overrides: [
      copilotEndpointsProvider.overrideWithValue(
        endpoints ?? _FakeCopilotEndpoints(),
      ),
    ],
  );
  return container;
}

void main() {
  // ==========================================================================
  // Provider chain tests
  // ==========================================================================
  group('copilotEndpointsProvider', () {
    test('resolves to a CopilotEndpoints instance', () {
      // This test verifies the provider compiles and returns the right type
      // when given proper overrides.
      final container = _createContainer();
      final endpoints = container.read(copilotEndpointsProvider);
      expect(endpoints, isA<CopilotEndpoints>());
    });
  });

  group('copilotStateProvider', () {
    test('resolves to a CopilotStateNotifier', () {
      final container = _createContainer();
      final notifier = container.read(copilotStateProvider.notifier);
      expect(notifier, isA<CopilotStateNotifier>());
    });

    test('initial state is CopilotIdle', () {
      final container = _createContainer();
      final state = container.read(copilotStateProvider);
      expect(state, isA<CopilotIdle>());
    });
  });

  // ==========================================================================
  // CopilotStateNotifier
  // ==========================================================================
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

        expect(notifier.state, isA<CopilotIdle>());
        await notifier.sendMessage('find trucks');

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

      test('stores conversationId from response', () async {
        fakeEndpoints.onChat = () => const CopilotResponse(
              conversationId: 'conv-stored',
            );

        await notifier.sendMessage('test');

        expect(notifier.conversationId, 'conv-stored');
      });

      test('ignores empty utterance', () async {
        await notifier.sendMessage('   ');
        expect(notifier.state, isA<CopilotIdle>());
      });

      test('transitions to CopilotProcessing then CopilotError on failure',
          () async {
        fakeEndpoints.onChat = () => throw Exception('network error');

        await notifier.sendMessage('find trucks');

        expect(notifier.state, isA<CopilotError>());
        expect((notifier.state as CopilotError).messageKey,
            'copilot.error.unexpected');
      });

      test('transitions to CopilotCompleted with summaryKey null when no summary', 
          () async {
        fakeEndpoints.onChat = () => const CopilotResponse(
              conversationId: 'conv-4',
            );

        await notifier.sendMessage('test');

        final state = notifier.state;
        expect(state, isA<CopilotCompleted>());
        expect((state as CopilotCompleted).summaryKey, isNull);
      });
    });

    group('confirmPlan', () {
      test('with confirmationPhrase transitions to CopilotCompleted', () async {
        final plan = _planWithConfirmationLevels(
          levels: [3],
          confirmationPhrase: 'I understand',
        );
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

      test('transitions to CopilotExecuting intermediate state', () async {
        final plan = _planWithConfirmationLevels(levels: [2]);
        notifier = CopilotStateNotifier(fakeEndpoints)
          ..state = CopilotAwaitingConfirmation(plan: plan);
        fakeEndpoints.onConfirmPlan = () => {'status': 'completed'};

        // Listen for intermediate state
        final states = <CopilotMobileState>[];
        notifier.addListener((state) => states.add(state));

        await notifier.confirmPlan();

        // Should have passed through CopilotExecuting
        expect(states.any((s) => s is CopilotExecuting), isTrue);
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
        // First establish a conversation
        fakeEndpoints.onChat = () => const CopilotResponse(
              conversationId: 'conv-to-reset',
            );
        await notifier.sendMessage('test');
        expect(notifier.conversationId, 'conv-to-reset');

        notifier.reset();

        expect(notifier.state, isA<CopilotIdle>());
        expect(notifier.conversationId, isNull);
      });

      test('resets from any state to idle', () {
        // From error
        notifier = CopilotStateNotifier(fakeEndpoints)
          ..state = const CopilotError(messageKey: 'test');
        notifier.reset();
        expect(notifier.state, isA<CopilotIdle>());

        // From completed
        notifier.state = const CopilotCompleted();
        notifier.reset();
        expect(notifier.state, isA<CopilotIdle>());

        // From executing
        notifier.state = const CopilotExecuting();
        notifier.reset();
        expect(notifier.state, isA<CopilotIdle>());
      });
    });

    group('_handleResponse routing', () {
      test('clarification state takes priority over plan', () async {
        final plan = _planWithConfirmationLevels(
          levels: [2],
          requiresConfirmation: true,
        );
        fakeEndpoints.onChat = () => CopilotResponse(
              conversationId: 'conv-prior',
              plan: plan, // plan present
              clarificationQuestionKey:
                  'copilot.clarification.test', // but also clarification
            );

        await notifier.sendMessage('test');

        final state = notifier.state;
        expect(state, isA<CopilotAwaitingClarification>());
      });

      test('summary state when plan does not require confirmation', () async {
        final plan = _planWithConfirmationLevels(
          levels: [1],
          requiresConfirmation: false,
        );
        fakeEndpoints.onChat = () => CopilotResponse(
              conversationId: 'conv-sum',
              plan: plan,
              summaryKey: 'copilot.summary.done',
            );

        await notifier.sendMessage('test');

        final state = notifier.state;
        expect(state, isA<CopilotCompleted>());
        expect((state as CopilotCompleted).summaryKey, 'copilot.summary.done');
      });

      test('simple completed when plan has no confirmation and no summary',
          () async {
        fakeEndpoints.onChat = () => CopilotResponse(
              conversationId: 'conv-simple',
              plan: _planWithConfirmationLevels(
                levels: [1],
                requiresConfirmation: false,
              ),
            );

        await notifier.sendMessage('test');

        expect(notifier.state, isA<CopilotCompleted>());
      });
    });
  });
}
