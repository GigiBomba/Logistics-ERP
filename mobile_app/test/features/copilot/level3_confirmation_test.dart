import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/features/copilot/models/copilot_models.dart';

void main() {
  group('Copilot Level 3 Confirmation', () {
    test('isLevel3 returns true when a step has confirmationLevel >= 3', () {
      final plan = CopilotExecutionPlan(
        planId: 'plan-1',
        conversationId: 'conv-1',
        intent: const CopilotIntent(name: 'test'),
        confirmationPhrase: 'confirm dangerous action',
        steps: const [
          CopilotExecutionStep(stepId: 's1', toolName: 'test', confirmationLevel: 3),
        ],
      );
      expect(plan.isLevel3, isTrue);
      expect(plan.maxConfirmationLevel, 3);
      expect(plan.confirmationPhrase, 'confirm dangerous action');
    });

    test('isLevel3 returns false when all steps are Level 2 or below', () {
      final plan = CopilotExecutionPlan(
        planId: 'plan-2',
        conversationId: 'conv-2',
        intent: const CopilotIntent(name: 'test'),
        steps: const [
          CopilotExecutionStep(stepId: 's1', toolName: 'test', confirmationLevel: 2),
          CopilotExecutionStep(stepId: 's2', toolName: 'test2', confirmationLevel: 1),
        ],
      );
      expect(plan.isLevel3, isFalse);
      expect(plan.maxConfirmationLevel, 2);
    });

    test('fromJson parses confirmation_phrase', () {
      final json = {
        'plan_id': 'plan-3',
        'conversation_id': 'conv-3',
        'intent': {'name': 'test'},
        'confirmation_phrase': 'type this to confirm',
        'steps': [
          {'step_id': 's1', 'tool_name': 'test', 'confirmation_level': 3},
        ],
      };
      final plan = CopilotExecutionPlan.fromJson(json);
      expect(plan.confirmationPhrase, 'type this to confirm');
      expect(plan.isLevel3, isTrue);
    });

    test('toJson round-trips confirmation_phrase', () {
      final original = CopilotExecutionPlan(
        planId: 'plan-4',
        conversationId: 'conv-4',
        intent: const CopilotIntent(name: 'test'),
        confirmationPhrase: 'yes',
        steps: const [
          CopilotExecutionStep(stepId: 's1', toolName: 'test', confirmationLevel: 3),
        ],
      );
      final json = original.toJson();
      final restored = CopilotExecutionPlan.fromJson(json);
      expect(restored.confirmationPhrase, original.confirmationPhrase);
      expect(restored.isLevel3, original.isLevel3);
    });

    test('maxConfirmationLevel returns 0 for empty steps', () {
      final plan = CopilotExecutionPlan(
        planId: 'plan-5',
        conversationId: 'conv-5',
        intent: const CopilotIntent(name: 'test'),
      );
      expect(plan.maxConfirmationLevel, 0);
      expect(plan.isLevel3, isFalse);
    });
  });
}
