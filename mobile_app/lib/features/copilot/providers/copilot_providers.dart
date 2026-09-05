import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/network/endpoints/copilot_endpoints.dart';
import '../../../core/sync/action_queue.dart';
import '../models/copilot_models.dart';
import '../network/copilot_retry_policy.dart';
import '../notifications/copilot_notification_service.dart';
import '../storage/copilot_conversation_cache.dart';

// ── Foundation providers ─────────────────────────────────────────────────

final copilotEndpointsProvider = Provider<CopilotEndpoints>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  // Attach the §28.1 retry policy to the shared client exactly once —
  // transient failures are retried once with exponential backoff, 4xx /
  // deterministic errors are never retried.
  final hasRetryInterceptor = apiClient.dio.interceptors
      .any((i) => i is CopilotRetryInterceptor);
  if (!hasRetryInterceptor) {
    apiClient.dio.interceptors.add(CopilotRetryInterceptor(
      dio: apiClient.dio,
      policy: const CopilotRetryPolicy(),
    ));
  }
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
      state = CopilotError(messageKey: _classifyErrorKey(e));
    }
  }

  /// Maps a transport error to a user-facing i18n `message_key` (§28).
  ///
  /// A 503 (circuit breaker open, §23.1) surfaces as
  /// `copilot.error.circuit_open` so the notification bridge can alert the
  /// user; every other error collapses to the generic fallback key.
  static String _classifyErrorKey(Object error) {
    if (error is DioException) {
      final status = error.response?.statusCode;
      if (status == 503) {
        return CopilotEventKeys.circuitOpenMessageKey;
      }
    }
    return 'copilot.error.unexpected';
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

// ── Offline conversation cache (§32.3) ────────────────────────────────────

/// Provides the read-only conversation-history cache backed by the shared
/// [LocalDatabase] JSON store. Waits for [LocalDatabase.initialize] so the
/// cache never touches an uninitialised store.
final copilotCacheProvider =
    FutureProvider<CopilotConversationCache>((ref) async {
  final db = await ref.watch(localDatabaseProvider.future);
  return CopilotConversationCache(db);
});

// ── Conversation history (read-only results, §32.3) ───────────────────────

/// Possible states of conversation-history reads (§32.3).
sealed class CopilotHistoryState {
  const CopilotHistoryState();
}

class CopilotHistoryLoading extends CopilotHistoryState {
  const CopilotHistoryLoading();
}

class CopilotHistoryData extends CopilotHistoryState {
  /// The raw read-only payload (`listConversations` / `getConversation`).
  final Map<String, dynamic> data;

  /// `true` when served from the local cache instead of the live API.
  final bool isOffline;

  /// Always `true` — history is never mutated client-side.
  final bool isReadOnly;

  /// When the snapshot was cached (`null` for live results).
  final DateTime? cachedAt;

  const CopilotHistoryData({
    required this.data,
    this.isOffline = false,
    this.isReadOnly = true,
    this.cachedAt,
  });
}

class CopilotHistoryError extends CopilotHistoryState {
  final String messageKey;
  const CopilotHistoryError({required this.messageKey});
}

/// Fetches conversation history from the backend and caches read-only results
/// for offline reuse (§32.3).
///
/// When the network request fails, the cached snapshot is returned instead —
/// clearly flagged as offline/read-only so it is never presented as fresh.
class CopilotHistoryController extends StateNotifier<CopilotHistoryState> {
  final CopilotEndpoints _endpoints;
  final CopilotConversationCache _cache;

  CopilotHistoryController(this._endpoints, this._cache)
      : super(const CopilotHistoryLoading());

  /// Loads the conversation list. On network failure, falls back to the
  /// cached snapshot (if any, and not expired).
  Future<void> loadConversations() async {
    state = const CopilotHistoryLoading();
    try {
      final data = await _endpoints.listConversations();
      await _cache.cacheConversations(data);
      state = CopilotHistoryData(data: data);
    } catch (e) {
      final cached = await _cache.readCachedConversations();
      if (cached != null) {
        state = CopilotHistoryData(
          data: cached.data,
          isOffline: true,
          cachedAt: cached.cachedAt,
        );
      } else {
        state = const CopilotHistoryError(messageKey: 'copilot.error.unexpected');
      }
    }
  }

  /// Loads the message history for [conversationId]. On network failure,
  /// falls back to the cached snapshot (if any, and not expired).
  Future<void> loadConversation(String conversationId) async {
    state = const CopilotHistoryLoading();
    try {
      final data = await _endpoints.getConversation(conversationId);
      await _cache.cacheConversation(conversationId, data);
      state = CopilotHistoryData(data: data);
    } catch (e) {
      final cached = await _cache.readCachedConversation(conversationId);
      if (cached != null) {
        state = CopilotHistoryData(
          data: cached.data,
          isOffline: true,
          cachedAt: cached.cachedAt,
        );
      } else {
        state = const CopilotHistoryError(messageKey: 'copilot.error.unexpected');
      }
    }
  }

  /// Clears the offline cache and returns to the loading state.
  Future<void> clearCache() async {
    await _cache.clear();
    state = const CopilotHistoryLoading();
  }
}

final copilotHistoryProvider =
    FutureProvider<CopilotHistoryController>((ref) async {
  final endpoints = ref.watch(copilotEndpointsProvider);
  final cache = await ref.watch(copilotCacheProvider.future);
  return CopilotHistoryController(endpoints, cache);
});
