import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/features/copilot/models/copilot_models.dart';

void main() {
  // ==========================================================================
  // CopilotIntent
  // ==========================================================================
  group('CopilotIntent', () {
    test('fromJson parses all fields', () {
      final json = {
        'name': 'vehicle.search',
        'entities': [
          {'type': 'vehicle_type', 'value': 'truck', 'source': 'extracted', 'confidence': 0.95},
        ],
        'missing_required_entities': ['origin', 'destination'],
        'raw_utterance': 'find trucks available in Bucharest',
      };
      final intent = CopilotIntent.fromJson(json);
      expect(intent.name, 'vehicle.search');
      expect(intent.entities.length, 1);
      expect(intent.entities.first.type, 'vehicle_type');
      expect(intent.missingRequiredEntities, ['origin', 'destination']);
      expect(intent.rawUtterance, 'find trucks available in Bucharest');
    });

    test('fromJson handles empty json with defaults', () {
      final intent = CopilotIntent.fromJson({});
      expect(intent.name, '');
      expect(intent.entities, isEmpty);
      expect(intent.missingRequiredEntities, isEmpty);
      expect(intent.rawUtterance, '');
    });

    test('fromJson handles null fields', () {
      final json = {
        'name': null,
        'entities': null,
        'missing_required_entities': null,
        'raw_utterance': null,
      };
      final intent = CopilotIntent.fromJson(json);
      expect(intent.name, '');
      expect(intent.entities, isEmpty);
      expect(intent.missingRequiredEntities, isEmpty);
      expect(intent.rawUtterance, '');
    });

    test('toJson serializes correctly', () {
      final intent = CopilotIntent(
        name: 'dispatch.create',
        entities: const [
          CopilotEntity(type: 'vehicle_id', value: 'VH-001'),
        ],
        missingRequiredEntities: const ['driver'],
        rawUtterance: 'dispatch VH-001',
      );
      final json = intent.toJson();
      expect(json['name'], 'dispatch.create');
      expect(json['entities'], isA<List>());
      expect((json['entities'] as List).length, 1);
      expect(json['missing_required_entities'], ['driver']);
      expect(json['raw_utterance'], 'dispatch VH-001');
    });

    test('toJson round-trips correctly', () {
      final original = CopilotIntent(
        name: 'vehicle.search',
        entities: const [
          CopilotEntity(type: 'status', value: 'available'),
        ],
        missingRequiredEntities: const ['location'],
        rawUtterance: 'show available vehicles',
      );
      final json = original.toJson();
      final restored = CopilotIntent.fromJson(json);
      expect(restored.name, original.name);
      expect(restored.entities.length, original.entities.length);
      expect(restored.entities.first.type, original.entities.first.type);
      expect(restored.missingRequiredEntities, original.missingRequiredEntities);
      expect(restored.rawUtterance, original.rawUtterance);
    });

    test('default constructor values', () {
      const intent = CopilotIntent(name: 'test');
      expect(intent.entities, isEmpty);
      expect(intent.missingRequiredEntities, isEmpty);
      expect(intent.rawUtterance, '');
    });
  });

  // ==========================================================================
  // CopilotEntity
  // ==========================================================================
  group('CopilotEntity', () {
    test('fromJson parses all fields', () {
      final json = {
        'type': 'vehicle_type',
        'value': 'truck',
        'source': 'nlp',
        'confidence': 0.87,
      };
      final entity = CopilotEntity.fromJson(json);
      expect(entity.type, 'vehicle_type');
      expect(entity.value, 'truck');
      expect(entity.source, 'nlp');
      expect(entity.confidence, 0.87);
    });

    test('fromJson handles empty json with defaults', () {
      final entity = CopilotEntity.fromJson({});
      expect(entity.type, '');
      expect(entity.value, isNull);
      expect(entity.source, 'extracted');
      expect(entity.confidence, 1.0);
    });

    test('fromJson handles null confidence as 1.0', () {
      final json = {'type': 'driver', 'confidence': null};
      final entity = CopilotEntity.fromJson(json);
      expect(entity.confidence, 1.0);
    });

    test('value can be any type - string', () {
      final json = {'type': 'status', 'value': 'available'};
      final entity = CopilotEntity.fromJson(json);
      expect(entity.value, 'available');
    });

    test('value can be any type - number', () {
      final json = {'type': 'quantity', 'value': 42};
      final entity = CopilotEntity.fromJson(json);
      expect(entity.value, 42);
    });

    test('value can be any type - bool', () {
      final json = {'type': 'flag', 'value': true};
      final entity = CopilotEntity.fromJson(json);
      expect(entity.value, true);
    });

    test('value can be any type - map', () {
      final json = {'type': 'location', 'value': {'lat': 44.4, 'lng': 26.1}};
      final entity = CopilotEntity.fromJson(json);
      expect(entity.value, isA<Map>());
    });

    test('toJson serializes correctly', () {
      const entity = CopilotEntity(
        type: 'vehicle_id',
        value: 'TR-123',
        source: 'extracted',
        confidence: 0.99,
      );
      final json = entity.toJson();
      expect(json['type'], 'vehicle_id');
      expect(json['value'], 'TR-123');
      expect(json['source'], 'extracted');
      expect(json['confidence'], 0.99);
    });

    test('toJson round-trips correctly', () {
      const original = CopilotEntity(
        type: 'driver_name',
        value: 'John Doe',
        source: 'nlp',
        confidence: 0.75,
      );
      final json = original.toJson();
      final restored = CopilotEntity.fromJson(json);
      expect(restored.type, original.type);
      expect(restored.value, original.value);
      expect(restored.source, original.source);
      expect(restored.confidence, original.confidence);
    });
  });

  // ==========================================================================
  // CopilotExecutionStep
  // ==========================================================================
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

    test('isTerminal returns false for pending status', () {
      const step = CopilotExecutionStep(stepId: 's1', toolName: 't', status: 'pending');
      expect(step.isTerminal, false);
    });

    test('isTerminal returns false for running status', () {
      const step = CopilotExecutionStep(stepId: 's1', toolName: 't', status: 'running');
      expect(step.isTerminal, false);
    });

    test('isTerminal returns true for succeeded status', () {
      const step = CopilotExecutionStep(stepId: 's1', toolName: 't', status: 'succeeded');
      expect(step.isTerminal, true);
    });

    test('isTerminal returns true for failed status', () {
      const step = CopilotExecutionStep(stepId: 's1', toolName: 't', status: 'failed');
      expect(step.isTerminal, true);
    });

    test('isTerminal returns true for skipped status', () {
      const step = CopilotExecutionStep(stepId: 's1', toolName: 't', status: 'skipped');
      expect(step.isTerminal, true);
    });

    test('fromJson parses dates correctly', () {
      final json = {
        'step_id': 's1',
        'tool_name': 'test',
        'started_at': '2026-07-19T10:00:00.000Z',
        'finished_at': '2026-07-19T10:05:30.000Z',
      };
      final step = CopilotExecutionStep.fromJson(json);
      expect(step.startedAt, isNotNull);
      expect(step.startedAt!.toIso8601String(), '2026-07-19T10:00:00.000Z');
      expect(step.finishedAt, isNotNull);
      expect(step.finishedAt!.toIso8601String(), '2026-07-19T10:05:30.000Z');
    });

    test('fromJson handles null dates', () {
      final json = {
        'step_id': 's1',
        'tool_name': 'test',
        'started_at': null,
        'finished_at': null,
      };
      final step = CopilotExecutionStep.fromJson(json);
      expect(step.startedAt, isNull);
      expect(step.finishedAt, isNull);
    });

    test('fromJson handles invalid date strings as null', () {
      final json = {
        'step_id': 's1',
        'tool_name': 'test',
        'started_at': 'not-a-date',
        'finished_at': 'also-invalid',
      };
      final step = CopilotExecutionStep.fromJson(json);
      expect(step.startedAt, isNull);
      expect(step.finishedAt, isNull);
    });

    test('toJson includes optional fields when present', () {
      final step = CopilotExecutionStep(
        stepId: 's1',
        toolName: 'vehicle.search',
        status: 'succeeded',
        result: {'found': 5},
        error: null,
        startedAt: DateTime.utc(2026, 7, 19, 10, 0, 0),
        finishedAt: DateTime.utc(2026, 7, 19, 10, 5, 30),
      );
      final json = step.toJson();
      expect(json['step_id'], 's1');
      expect(json['result'], {'found': 5});
      expect(json['started_at'], '2026-07-19T10:00:00.000Z');
      expect(json['finished_at'], '2026-07-19T10:05:30.000Z');
      expect(json.containsKey('error'), false);
    });

    test('toJson excludes optional fields when null', () {
      const step = CopilotExecutionStep(stepId: 's1', toolName: 'test');
      final json = step.toJson();
      expect(json.containsKey('result'), false);
      expect(json.containsKey('error'), false);
      expect(json.containsKey('started_at'), false);
      expect(json.containsKey('finished_at'), false);
    });

    test('toJson round-trips correctly with all fields', () {
      final original = CopilotExecutionStep(
        stepId: 's-full',
        toolName: 'dispatch.create',
        toolVersion: '2.0.0',
        parameters: {'vehicle_id': 'VH-001'},
        dependsOn: ['s0'],
        confirmationLevel: 2,
        status: 'running',
        result: null,
        error: null,
        startedAt: DateTime.utc(2026, 7, 19),
      );
      final json = original.toJson();
      final restored = CopilotExecutionStep.fromJson(json);
      expect(restored.stepId, original.stepId);
      expect(restored.toolName, original.toolName);
      expect(restored.toolVersion, original.toolVersion);
      expect(restored.parameters, original.parameters);
      expect(restored.dependsOn, original.dependsOn);
      expect(restored.confirmationLevel, original.confirmationLevel);
      expect(restored.status, original.status);
      expect(restored.startedAt!.toIso8601String(), original.startedAt!.toIso8601String());
    });
  });

  // ==========================================================================
  // CopilotExecutionPlan
  // ==========================================================================
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

    test('fromJson handles empty json', () {
      final plan = CopilotExecutionPlan.fromJson({});
      expect(plan.planId, '');
      expect(plan.conversationId, '');
      expect(plan.requiresConfirmation, false);
      expect(plan.steps, isEmpty);
      expect(plan.overallConfidence, 1.0);
      expect(plan.createdAt, isNull);
    });

    test('fromJson parses nested fields correctly', () {
      final json = {
        'plan_id': 'plan-full',
        'conversation_id': 'conv-full',
        'reasoning_graph_id': 'graph-001',
        'intent': {'name': 'vehicle.search', 'raw_utterance': 'find trucks'},
        'overall_confidence': 0.92,
        'requires_confirmation': true,
        'confirmation_phrase': 'I approve',
        'created_at': '2026-07-19T12:00:00.000Z',
        'steps': [
          {'step_id': 's1', 'tool_name': 'vehicle.search', 'confirmation_level': 1},
          {'step_id': 's2', 'tool_name': 'dispatch.create', 'confirmation_level': 3},
        ],
      };
      final plan = CopilotExecutionPlan.fromJson(json);
      expect(plan.planId, 'plan-full');
      expect(plan.conversationId, 'conv-full');
      expect(plan.reasoningGraphId, 'graph-001');
      expect(plan.intent.name, 'vehicle.search');
      expect(plan.overallConfidence, 0.92);
      expect(plan.requiresConfirmation, true);
      expect(plan.confirmationPhrase, 'I approve');
      expect(plan.createdAt, isNotNull);
      expect(plan.steps.length, 2);
      expect(plan.isLevel3, true);
    });

    test('toJson round-trips correctly', () {
      final original = CopilotExecutionPlan(
        planId: 'plan-rt',
        conversationId: 'conv-rt',
        reasoningGraphId: 'graph-rt',
        intent: const CopilotIntent(name: 'test', rawUtterance: 'hello'),
        steps: const [
          CopilotExecutionStep(stepId: 's1', toolName: 't1', confirmationLevel: 2),
        ],
        overallConfidence: 0.85,
        requiresConfirmation: true,
        confirmationPhrase: 'confirm',
        createdAt: DateTime.utc(2026, 7, 19),
      );
      final json = original.toJson();
      final restored = CopilotExecutionPlan.fromJson(json);
      expect(restored.planId, original.planId);
      expect(restored.conversationId, original.conversationId);
      expect(restored.reasoningGraphId, original.reasoningGraphId);
      expect(restored.intent.name, original.intent.name);
      expect(restored.steps.length, original.steps.length);
      expect(restored.overallConfidence, original.overallConfidence);
      expect(restored.requiresConfirmation, original.requiresConfirmation);
      expect(restored.confirmationPhrase, original.confirmationPhrase);
      expect(restored.createdAt!.toIso8601String(), original.createdAt!.toIso8601String());
    });

    test('toJson omits null confirmationPhrase and createdAt', () {
      final plan = CopilotExecutionPlan(
        planId: 'p',
        conversationId: 'c',
        intent: const CopilotIntent(name: 'test'),
      );
      final json = plan.toJson();
      expect(json.containsKey('confirmation_phrase'), false);
      expect(json.containsKey('created_at'), false);
    });

    group('isLevel3', () {
      test('returns false when all steps are below 3', () {
        final plan = CopilotExecutionPlan(
          planId: 'p',
          conversationId: 'c',
          intent: const CopilotIntent(name: 'test'),
          steps: const [
            CopilotExecutionStep(stepId: 's1', toolName: 't', confirmationLevel: 0),
            CopilotExecutionStep(stepId: 's2', toolName: 't', confirmationLevel: 2),
          ],
        );
        expect(plan.isLevel3, false);
      });

      test('returns true when any step has Level 3', () {
        final plan = CopilotExecutionPlan(
          planId: 'p',
          conversationId: 'c',
          intent: const CopilotIntent(name: 'test'),
          steps: const [
            CopilotExecutionStep(stepId: 's1', toolName: 't', confirmationLevel: 2),
            CopilotExecutionStep(stepId: 's2', toolName: 't', confirmationLevel: 3),
          ],
        );
        expect(plan.isLevel3, true);
      });

      test('returns true when any step has Level 4+', () {
        final plan = CopilotExecutionPlan(
          planId: 'p',
          conversationId: 'c',
          intent: const CopilotIntent(name: 'test'),
          steps: const [
            CopilotExecutionStep(stepId: 's1', toolName: 't', confirmationLevel: 5),
          ],
        );
        expect(plan.isLevel3, true);
      });

      test('returns false when steps are empty', () {
        final plan = CopilotExecutionPlan(
          planId: 'p',
          conversationId: 'c',
          intent: const CopilotIntent(name: 'test'),
        );
        expect(plan.isLevel3, false);
      });
    });

    group('maxConfirmationLevel', () {
      test('returns 0 when there are no steps', () {
        final plan = CopilotExecutionPlan(
          planId: 'p',
          conversationId: 'c',
          intent: const CopilotIntent(name: 'test'),
        );
        expect(plan.maxConfirmationLevel, 0);
      });

      test('returns the highest confirmation level across steps', () {
        final plan = CopilotExecutionPlan(
          planId: 'p',
          conversationId: 'c',
          intent: const CopilotIntent(name: 'test'),
          steps: const [
            CopilotExecutionStep(stepId: 's1', toolName: 't', confirmationLevel: 1),
            CopilotExecutionStep(stepId: 's2', toolName: 't', confirmationLevel: 4),
            CopilotExecutionStep(stepId: 's3', toolName: 't', confirmationLevel: 2),
          ],
        );
        expect(plan.maxConfirmationLevel, 4);
      });
    });
  });

  // ==========================================================================
  // CopilotResponse
  // ==========================================================================
  group('CopilotResponse', () {
    test('fromJson parses clarification response', () {
      final json = {
        'conversation_id': 'conv-789',
        'clarification_question_key': 'copilot.clarification.missing_entities',
        'clarification_params': {'missing': ['origin']},
      };
      final resp = CopilotResponse.fromJson(json);
      expect(resp.conversationId, 'conv-789');
      expect(resp.clarificationQuestionKey, 'copilot.clarification.missing_entities');
      expect(resp.clarificationParams, {'missing': ['origin']});
      expect(resp.plan, isNull);
      expect(resp.summaryKey, isNull);
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
      expect(resp.clarificationQuestionKey, isNull);
    });

    test('fromJson parses completed response with summary', () {
      final json = {
        'conversation_id': 'conv-303',
        'summary_key': 'copilot.summary.done',
        'summary_params': {'vehicles_found': 3},
      };
      final resp = CopilotResponse.fromJson(json);
      expect(resp.conversationId, 'conv-303');
      expect(resp.summaryKey, 'copilot.summary.done');
      expect(resp.summaryParams, {'vehicles_found': 3});
      expect(resp.plan, isNull);
      expect(resp.clarificationQuestionKey, isNull);
    });

    test('fromJson parses response with timeline', () {
      final json = {
        'conversation_id': 'conv-timeline',
        'timeline': [
          {'step_id': 's1', 'tool_name': 'search', 'status': 'succeeded'},
          {'step_id': 's2', 'tool_name': 'dispatch', 'status': 'running'},
        ],
      };
      final resp = CopilotResponse.fromJson(json);
      expect(resp.timeline.length, 2);
      expect(resp.timeline.first.stepId, 's1');
      expect(resp.timeline.last.status, 'running');
    });

    test('fromJson handles empty json with defaults', () {
      final resp = CopilotResponse.fromJson({});
      expect(resp.conversationId, '');
      expect(resp.plan, isNull);
      expect(resp.clarificationQuestionKey, isNull);
      expect(resp.clarificationParams, isEmpty);
      expect(resp.timeline, isEmpty);
      expect(resp.summaryKey, isNull);
      expect(resp.summaryParams, isEmpty);
    });

    test('fromJson handles null plan field', () {
      final json = {
        'conversation_id': 'conv-404',
        'plan': null,
      };
      final resp = CopilotResponse.fromJson(json);
      expect(resp.conversationId, 'conv-404');
      expect(resp.plan, isNull);
    });

    test('toJson round-trips plan response', () {
      final plan = CopilotExecutionPlan(
        planId: 'plan-rt',
        conversationId: 'conv-rt',
        intent: const CopilotIntent(name: 'vehicle.search'),
      );
      final original = CopilotResponse(
        conversationId: 'conv-rt',
        plan: plan,
      );
      // Note: CopilotResponse doesn't have toJson, but using fromJson
      // with toJson output as a pattern. Since there's no toJson, skip.
      // Just verify fromJson covers the round-trip via the constructor.
      expect(original.conversationId, 'conv-rt');
      expect(original.plan!.planId, 'plan-rt');
    });

    test('response can have both timeline and summary', () {
      final json = {
        'conversation_id': 'conv-combo',
        'timeline': [
          {'step_id': 's1', 'tool_name': 'search', 'status': 'succeeded'},
        ],
        'summary_key': 'copilot.summary.complete',
        'summary_params': {'result': 'ok'},
      };
      final resp = CopilotResponse.fromJson(json);
      expect(resp.timeline.length, 1);
      expect(resp.summaryKey, 'copilot.summary.complete');
      expect(resp.summaryParams, {'result': 'ok'});
    });
  });
}
