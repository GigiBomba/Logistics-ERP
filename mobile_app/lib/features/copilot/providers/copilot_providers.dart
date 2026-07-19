import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/network/endpoints/copilot_endpoints.dart';
import '../models/copilot_models.dart';

// ── Foundation providers ─────────────────────────────────────────────────

final copilotEndpointsProvider = Provider<CopilotEndpoints>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  return CopilotEndpoints(apiClient);
});

// ── State providers ──────────────────────────────────────────────────────

/// The possible states of the Co-Pilot mobile interface (§32.1).
///
/// Mirrors the backend's own state machine (§7) — the mobile app is a
/// renderer of server-authoritative state, not an independent source of truth.
sealed class CopilotMobileState {
  const CopilotMobileState();
}

class CopilotIdle extends CopilotMobileState {
  const CopilotIdle();
}

class CopilotListening extends CopilotMobileState {
  const CopilotListening();
}

class CopilotProcessing extends CopilotMobileState {
  const CopilotProcessing();
}

class CopilotAwaitingClarification extends CopilotMobileState {
  final String questionKey;
  final Map<String, dynamic> params;
  const CopilotAwaitingClarification({
    required this.questionKey,
    this.params = const {},
  });
}

class CopilotAwaitingConfirmation extends CopilotMobileState {
  final CopilotExecutionPlan plan;
  const CopilotAwaitingConfirmation({required this.plan});
}

class CopilotExecuting extends CopilotMobileState {
  final List<CopilotExecutionStep> timeline;
  const CopilotExecuting({this.timeline = const []});
}

class CopilotCompleted extends CopilotMobileState {
  final String? summaryKey;
  final Map<String, dynamic> params;
  const CopilotCompleted({this.summaryKey, this.params = const {}});
}

class CopilotError extends CopilotMobileState {
  final String messageKey;
  const CopilotError({required this.messageKey});
}

/// StateNotifier managing the Co-Pilot conversation lifecycle.
///
/// Rules (§32.1):
/// 1. Only renders states the backend actually produced
/// 2. No locally-invented states for Level 1+ (optimistic UI OK for Level 0)
/// 3. Timeline updates rebuild only the changed step widget, not the whole screen
class CopilotStateNotifier extends StateNotifier<CopilotMobileState> {
  final CopilotEndpoints _endpoints;
  String? _conversationId;

  CopilotStateNotifier(this._endpoints) : super(const CopilotIdle());

  String? get conversationId => _conversationId;

  /// Submit a text utterance to the Co-Pilot.
  Future<void> sendMessage(String utterance) async {
    if (utterance.trim().isEmpty) return;
    state = const CopilotProcessing();
    try {
      final response = await _endpoints.chat(
        utterance: utterance,
        conversationId: _conversationId,
      );
      _conversationId = response.conversationId;
      _handleResponse(response);
    } catch (e) {
      state = const CopilotError(messageKey: 'copilot.error.unexpected');
    }
  }

  /// Confirm a plan that's awaiting confirmation.
  ///
  /// For Level 3 confirmation, pass the typed [confirmationPhrase].
  Future<void> confirmPlan({String? confirmationPhrase}) async {
    final current = state;
    if (current is! CopilotAwaitingConfirmation) return;
    state = CopilotExecuting(timeline: current.plan.steps);
    try {
      await _endpoints.confirmPlan(
        current.plan.planId,
        null,
        confirmationPhrase: confirmationPhrase,
      );
      state = const CopilotCompleted(summaryKey: 'copilot.summary.confirmed');
    } catch (e) {
      state = const CopilotError(messageKey: 'copilot.error.unexpected');
    }
  }

  /// Cancel the current plan.
  Future<void> cancelPlan() async {
    final current = state;
    if (current is! CopilotAwaitingConfirmation) return;
    try {
      await _endpoints.cancelPlan(current.plan.planId);
      state = const CopilotIdle();
    } catch (e) {
      state = const CopilotError(messageKey: 'copilot.error.unexpected');
    }
  }

  void _handleResponse(CopilotResponse response) {
    if (response.clarificationQuestionKey != null) {
      state = CopilotAwaitingClarification(
        questionKey: response.clarificationQuestionKey!,
        params: response.clarificationParams,
      );
    } else if (response.plan != null && response.plan!.requiresConfirmation) {
      state = CopilotAwaitingConfirmation(plan: response.plan!);
    } else if (response.summaryKey != null) {
      state = CopilotCompleted(
        summaryKey: response.summaryKey,
        params: response.summaryParams,
      );
    } else {
      state = const CopilotCompleted();
    }
  }

  void reset() {
    _conversationId = null;
    state = const CopilotIdle();
  }
}

final copilotStateProvider =
    StateNotifierProvider<CopilotStateNotifier, CopilotMobileState>((ref) {
  final endpoints = ref.watch(copilotEndpointsProvider);
  return CopilotStateNotifier(endpoints);
});
