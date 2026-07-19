import 'dart:async';

import 'package:dio/dio.dart';

import '../../../features/copilot/models/copilot_models.dart';
import '../api_client.dart';
import '../websocket_client.dart';

/// Endpoints for the AI Co-Pilot API (§30).
///
/// All endpoints sit under /api/v1/copilot/* and require JWT auth.
class CopilotEndpoints {
  final ApiClient _client;

  CopilotEndpoints(this._client);

  // ── Chat (§16, §30) ───────────────────────────────────────────────────

  /// Submit a text utterance through the Co-Pilot pipeline.
  Future<CopilotResponse> chat({
    required String utterance,
    String? conversationId,
    String language = 'en',
    CancelToken? cancelToken,
  }) async {
    final response = await _client.dio.post(
      '/api/v1/copilot/chat',
      data: {
        'utterance': utterance,
        if (conversationId != null) 'conversation_id': conversationId,
        'language': language,
      },
      cancelToken: cancelToken,
    );
    return CopilotResponse.fromJson(
        response.data as Map<String, dynamic>);
  }

  // ── Voice Input (§3.2, §30) ───────────────────────────────────────────

  /// Submit a voice transcript through the same pipeline as chat.
  Future<CopilotResponse> voiceInput({
    required String transcript,
    String? conversationId,
    String language = 'en',
    CancelToken? cancelToken,
  }) async {
    final response = await _client.dio.post(
      '/api/v1/copilot/voice',
      data: {
        'utterance': transcript,
        if (conversationId != null) 'conversation_id': conversationId,
        'language': language,
      },
      cancelToken: cancelToken,
    );
    return CopilotResponse.fromJson(
        response.data as Map<String, dynamic>);
  }

  // ── Plans (§7, §12.1, §30) ────────────────────────────────────────────

  /// Get the full execution plan with step-by-step timeline.
  Future<CopilotExecutionPlan> getPlan(String planId) async {
    final response = await _client.get(
      '/api/v1/copilot/plans/$planId',
    );
    // The endpoint returns a plan-shaped response or fallback
    final data = response.data as Map<String, dynamic>;
    if (data.containsKey('plan_id')) {
      return CopilotExecutionPlan.fromJson(data);
    }
    throw Exception('Plan $planId not found');
  }

  /// Confirm and execute a plan awaiting confirmation.
  ///
  /// For Level 3 confirmation, pass the typed [confirmationPhrase].
  Future<Map<String, dynamic>> confirmPlan(
    String planId,
    CancelToken? cancelToken, {
    String? confirmationPhrase,
  }) async {
    final data = <String, dynamic>{};
    if (confirmationPhrase != null) {
      data['confirmation_phrase'] = confirmationPhrase;
    }
    final response = await _client.dio.post(
      '/api/v1/copilot/plans/$planId/confirm',
      data: data.isNotEmpty ? data : null,
      cancelToken: cancelToken,
    );
    return response.data as Map<String, dynamic>;
  }

  /// Cancel an in-flight plan.
  Future<Map<String, dynamic>> cancelPlan(String planId) async {
    final response = await _client.post(
      '/api/v1/copilot/plans/$planId/cancel',
    );
    return response.data as Map<String, dynamic>;
  }

  /// Undo a completed step within the 30-minute window (§22 item 4).
  Future<Map<String, dynamic>> undoPlan(String planId) async {
    final response = await _client.post(
      '/api/v1/copilot/plans/$planId/undo',
    );
    return response.data as Map<String, dynamic>;
  }

  // ── Conversations (§11, §30) ──────────────────────────────────────────

  /// List the calling user's conversations.
  Future<Map<String, dynamic>> listConversations({
    int limit = 20,
    String? cursor,
  }) async {
    final queryParams = <String, dynamic>{'limit': limit};
    if (cursor != null) queryParams['cursor'] = cursor;
    final response = await _client.get(
      '/api/v1/copilot/conversations',
      queryParameters: queryParams,
    );
    return response.data as Map<String, dynamic>;
  }

  /// Get details for a specific conversation.
  Future<Map<String, dynamic>> getConversation(
      String conversationId) async {
    final response = await _client.get(
      '/api/v1/copilot/conversations/$conversationId',
    );
    return response.data as Map<String, dynamic>;
  }

  // ── Insights (§18, §30) ───────────────────────────────────────────────

  /// List proactive insights for the review queue.
  Future<Map<String, dynamic>> listInsights({
    int limit = 20,
    String? statusFilter,
  }) async {
    final queryParams = <String, dynamic>{'limit': limit};
    if (statusFilter != null) queryParams['status_filter'] = statusFilter;
    final response = await _client.get(
      '/api/v1/copilot/insights',
      queryParameters: queryParams,
    );
    return response.data as Map<String, dynamic>;
  }

  // ── WebSocket (§12.1, §15.1) ──────────────────────────────────────────

  /// Stream real-time plan execution updates via WebSocket.
  ///
  /// Returns a broadcast stream of timeline updates that emits
  /// [CopilotExecutionStep] status changes as they happen.
  /// Reuses the existing [WebSocketClient] infrastructure.
  Stream<Map<String, dynamic>> watchPlanTimeline({
    required String baseUrl,
    required String conversationId,
    required String token,
  }) {
    final wsBase = baseUrl.replaceFirst('https://', 'wss://').replaceFirst('http://', 'ws://');
    final wsUrl = '$wsBase/api/v1/copilot/plans/$conversationId/timeline/ws';
    final wsClient = WebSocketClient();
    // Fire-and-forget connect — errors surface on the stream.
    wsClient.connect(wsUrl, token);

    // Automatically dispose the WebSocket client when the stream subscription
    // is cancelled to prevent resource leaks.
    final stream = wsClient.messages;
    final controller = StreamController<Map<String, dynamic>>.broadcast(
      onCancel: () => wsClient.dispose(),
    );
    stream.listen(
      (data) => controller.add(data),
      onError: (e) {
        controller.addError(e);
        wsClient.dispose();
      },
      onDone: () {
        controller.close();
        wsClient.dispose();
      },
    );
    return controller.stream;
  }
}
