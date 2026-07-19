/// Data models for the AI Co-Pilot (§32).
///
/// These mirror the backend schemas from Operion_AI_CoPilot_Blueprint_V4.md §4.
/// The mobile client is a renderer of server-authoritative state — these models
/// are deserialized from API responses, never mutated optimistically for Level 1+.

class CopilotIntent {
  final String name;
  final List<CopilotEntity> entities;
  final List<String> missingRequiredEntities;
  final String rawUtterance;

  const CopilotIntent({
    required this.name,
    this.entities = const [],
    this.missingRequiredEntities = const [],
    this.rawUtterance = '',
  });

  factory CopilotIntent.fromJson(Map<String, dynamic> json) => CopilotIntent(
    name: json['name'] as String? ?? '',
    entities: (json['entities'] as List<dynamic>?)
            ?.map((e) => CopilotEntity.fromJson(e as Map<String, dynamic>))
            .toList() ??
        [],
    missingRequiredEntities: (json['missing_required_entities'] as List<dynamic>?)
            ?.map((e) => e as String)
            .toList() ??
        [],
    rawUtterance: json['raw_utterance'] as String? ?? '',
  );

  Map<String, dynamic> toJson() => {
    'name': name,
    'entities': entities.map((e) => e.toJson()).toList(),
    'missing_required_entities': missingRequiredEntities,
    'raw_utterance': rawUtterance,
  };
}

class CopilotEntity {
  final String type;
  final dynamic value;
  final String source;
  final double confidence;

  const CopilotEntity({
    required this.type,
    this.value,
    this.source = 'extracted',
    this.confidence = 1.0,
  });

  factory CopilotEntity.fromJson(Map<String, dynamic> json) => CopilotEntity(
    type: json['type'] as String? ?? '',
    value: json['value'],
    source: json['source'] as String? ?? 'extracted',
    confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
  );

  Map<String, dynamic> toJson() => {
    'type': type,
    'value': value,
    'source': source,
    'confidence': confidence,
  };
}

class CopilotExecutionStep {
  final String stepId;
  final String toolName;
  final String toolVersion;
  final Map<String, dynamic> parameters;
  final List<String> dependsOn;
  final int confirmationLevel;
  final String status;
  final Map<String, dynamic>? result;
  final String? error;
  final DateTime? startedAt;
  final DateTime? finishedAt;

  const CopilotExecutionStep({
    required this.stepId,
    required this.toolName,
    this.toolVersion = '1.0.0',
    this.parameters = const {},
    this.dependsOn = const [],
    this.confirmationLevel = 0,
    this.status = 'pending',
    this.result,
    this.error,
    this.startedAt,
    this.finishedAt,
  });

  factory CopilotExecutionStep.fromJson(Map<String, dynamic> json) =>
      CopilotExecutionStep(
        stepId: json['step_id'] as String? ?? '',
        toolName: json['tool_name'] as String? ?? '',
        toolVersion: json['tool_version'] as String? ?? '1.0.0',
        parameters: json['parameters'] as Map<String, dynamic>? ?? {},
        dependsOn: (json['depends_on'] as List<dynamic>?)
                ?.map((e) => e as String)
                .toList() ??
            [],
        confirmationLevel: json['confirmation_level'] as int? ?? 0,
        status: json['status'] as String? ?? 'pending',
        result: json['result'] as Map<String, dynamic>?,
        error: json['error'] as String?,
        startedAt: json['started_at'] != null
            ? DateTime.tryParse(json['started_at'] as String)
            : null,
        finishedAt: json['finished_at'] != null
            ? DateTime.tryParse(json['finished_at'] as String)
            : null,
      );

  bool get isTerminal =>
      status == 'succeeded' || status == 'failed' || status == 'skipped';

  Map<String, dynamic> toJson() => {
    'step_id': stepId,
    'tool_name': toolName,
    'tool_version': toolVersion,
    'parameters': parameters,
    'depends_on': dependsOn,
    'confirmation_level': confirmationLevel,
    'status': status,
    if (result != null) 'result': result,
    if (error != null) 'error': error,
    if (startedAt != null) 'started_at': startedAt!.toIso8601String(),
    if (finishedAt != null) 'finished_at': finishedAt!.toIso8601String(),
  };
}

class CopilotExecutionPlan {
  final String planId;
  final String conversationId;
  final String reasoningGraphId;
  final CopilotIntent intent;
  final List<CopilotExecutionStep> steps;
  final double overallConfidence;
  final bool requiresConfirmation;
  final String? confirmationPhrase;
  final DateTime? createdAt;

  const CopilotExecutionPlan({
    required this.planId,
    required this.conversationId,
    this.reasoningGraphId = '',
    required this.intent,
    this.steps = const [],
    this.overallConfidence = 1.0,
    this.requiresConfirmation = false,
    this.confirmationPhrase,
    this.createdAt,
  });

  /// Returns true if any step requires Level 3 confirmation (typed phrase).
  bool get isLevel3 => steps.any((s) => s.confirmationLevel >= 3);

  /// Returns the highest confirmation level across all steps.
  int get maxConfirmationLevel =>
      steps.fold(0, (max, s) => s.confirmationLevel > max ? s.confirmationLevel : max);

  factory CopilotExecutionPlan.fromJson(Map<String, dynamic> json) =>
      CopilotExecutionPlan(
        planId: json['plan_id'] as String? ?? '',
        conversationId: json['conversation_id'] as String? ?? '',
        reasoningGraphId: json['reasoning_graph_id'] as String? ?? '',
        intent: CopilotIntent.fromJson(
            json['intent'] as Map<String, dynamic>? ?? {}),
        steps: (json['steps'] as List<dynamic>?)
                ?.map((e) =>
                    CopilotExecutionStep.fromJson(e as Map<String, dynamic>))
                .toList() ??
            [],
        overallConfidence:
            (json['overall_confidence'] as num?)?.toDouble() ?? 1.0,
        requiresConfirmation: json['requires_confirmation'] as bool? ?? false,
        confirmationPhrase: json['confirmation_phrase'] as String?,
        createdAt: json['created_at'] != null
            ? DateTime.tryParse(json['created_at'] as String)
            : null,
      );

  Map<String, dynamic> toJson() => {
    'plan_id': planId,
    'conversation_id': conversationId,
    'reasoning_graph_id': reasoningGraphId,
    'intent': intent.toJson(),
    'steps': steps.map((e) => e.toJson()).toList(),
    'overall_confidence': overallConfidence,
    'requires_confirmation': requiresConfirmation,
    if (confirmationPhrase != null) 'confirmation_phrase': confirmationPhrase,
    if (createdAt != null) 'created_at': createdAt!.toIso8601String(),
  };
}

class CopilotResponse {
  final String conversationId;
  final CopilotExecutionPlan? plan;
  final String? clarificationQuestionKey;
  final Map<String, dynamic> clarificationParams;
  final List<CopilotExecutionStep> timeline;
  final String? summaryKey;
  final Map<String, dynamic> summaryParams;

  const CopilotResponse({
    required this.conversationId,
    this.plan,
    this.clarificationQuestionKey,
    this.clarificationParams = const {},
    this.timeline = const [],
    this.summaryKey,
    this.summaryParams = const {},
  });

  factory CopilotResponse.fromJson(Map<String, dynamic> json) =>
      CopilotResponse(
        conversationId: json['conversation_id'] as String? ?? '',
        plan: json['plan'] != null
            ? CopilotExecutionPlan.fromJson(
                json['plan'] as Map<String, dynamic>)
            : null,
        clarificationQuestionKey:
            json['clarification_question_key'] as String?,
        clarificationParams: json['clarification_params']
                as Map<String, dynamic>? ??
            {},
        timeline: (json['timeline'] as List<dynamic>?)
                ?.map((e) =>
                    CopilotExecutionStep.fromJson(e as Map<String, dynamic>))
                .toList() ??
            [],
        summaryKey: json['summary_key'] as String?,
        summaryParams:
            json['summary_params'] as Map<String, dynamic>? ?? {},
      );
}
