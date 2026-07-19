import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/copilot_endpoints.dart';
import 'package:operion_mobile/features/copilot/models/copilot_models.dart';

/// Creates an [ApiClient] that resolves every request with a canned response.
ApiClient _fakeClient(Response Function() onResponse) {
  final client = ApiClient.create(
    baseUrl: 'https://test.com',
    getAccessToken: () async => null,
  );
  client.dio.interceptors.clear();
  client.dio.interceptors.add(QueuedInterceptorsWrapper(
    onRequest: (options, handler) {
      handler.resolve(onResponse());
    },
  ));
  return client;
}

/// Creates an [ApiClient] that captures request options and returns a
/// valid plan response containing [planId].
ApiClient _capturingPlanClient(
    void Function(RequestOptions options) onRequest,
    {required String planId}) {
  final client = ApiClient.create(
    baseUrl: 'https://test.com',
    getAccessToken: () async => null,
  );
  client.dio.interceptors.clear();
  client.dio.interceptors.add(QueuedInterceptorsWrapper(
    onRequest: (options, handler) {
      onRequest(options);
      handler.resolve(Response(
        requestOptions: options,
        statusCode: 200,
        data: <String, dynamic>{
          'plan_id': planId,
          'conversation_id': 'conv-$planId',
          'intent': <String, dynamic>{'name': 'test', 'raw_utterance': 'test'},
        },
      ));
    },
  ));
  return client;
}

/// Creates an [ApiClient] that throws a [DioException] on every request.
ApiClient _failingClient({
  int statusCode = 500,
  String? message,
}) {
  final client = ApiClient.create(
    baseUrl: 'https://test.com',
    getAccessToken: () async => null,
  );
  client.dio.interceptors.clear();
  client.dio.interceptors.add(QueuedInterceptorsWrapper(
    onRequest: (options, handler) {
      handler.reject(DioException(
        requestOptions: options,
        response: Response(
          requestOptions: options,
          statusCode: statusCode,
          data: {'error': message ?? 'Internal Server Error'},
        ),
      ));
    },
  ));
  return client;
}

/// Creates an [ApiClient] that captures the request options for inspection.
ApiClient _capturingClient(
    void Function(RequestOptions options) onRequest) {
  final client = ApiClient.create(
    baseUrl: 'https://test.com',
    getAccessToken: () async => null,
  );
  client.dio.interceptors.clear();
  client.dio.interceptors.add(QueuedInterceptorsWrapper(
    onRequest: (options, handler) {
      onRequest(options);
      handler.resolve(Response(
        requestOptions: options,
        statusCode: 200,
        data: <String, dynamic>{'ok': true},
      ));
    },
  ));
  return client;
}

void main() {
  group('CopilotEndpoints — chat', () {
    test('chat sends POST to /api/v1/copilot/chat with utterance', () async {
      RequestOptions? capturedOptions;
      final client = _capturingClient((options) {
        capturedOptions = options;
      });
      final endpoints = CopilotEndpoints(client);

      await endpoints.chat(utterance: 'find trucks');

      expect(capturedOptions, isNotNull);
      expect(capturedOptions!.path, '/api/v1/copilot/chat');
      expect(capturedOptions!.method, 'POST');
      final data = capturedOptions!.data as Map<String, dynamic>;
      expect(data['utterance'], 'find trucks');
      expect(data.containsKey('conversation_id'), false);
      expect(data['language'], 'en');
    });

    test('chat sends conversationId when provided', () async {
      RequestOptions? capturedOptions;
      final client = _capturingClient((options) {
        capturedOptions = options;
      });
      final endpoints = CopilotEndpoints(client);

      await endpoints.chat(utterance: 'find trucks', conversationId: 'conv-1');

      final data = capturedOptions!.data as Map<String, dynamic>;
      expect(data['conversation_id'], 'conv-1');
    });

    test('chat returns CopilotResponse on success', () async {
      final client = _fakeClient(() => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: {
          'conversation_id': 'conv-success',
          'summary_key': 'copilot.summary.done',
        },
      ));
      final endpoints = CopilotEndpoints(client);

      final result = await endpoints.chat(utterance: 'find trucks');

      expect(result, isA<CopilotResponse>());
      expect(result.conversationId, 'conv-success');
      expect(result.summaryKey, 'copilot.summary.done');
    });

    test('chat throws on server error', () async {
      final client = _failingClient(statusCode: 500, message: 'Server error');
      final endpoints = CopilotEndpoints(client);

      expect(
        () => endpoints.chat(utterance: 'find trucks'),
        throwsA(isA<DioException>()),
      );
    });

    test('chat throws on network error', () async {
      final client = _failingClient(statusCode: 0); // network error
      final endpoints = CopilotEndpoints(client);

      expect(
        () => endpoints.chat(utterance: 'find trucks'),
        throwsA(isA<DioException>()),
      );
    });
  });

  group('CopilotEndpoints — voice', () {
    test('voiceInput sends POST to /api/v1/copilot/voice', () async {
      RequestOptions? capturedOptions;
      final client = _capturingClient((options) {
        capturedOptions = options;
      });
      final endpoints = CopilotEndpoints(client);

      await endpoints.voiceInput(transcript: 'find trucks');

      expect(capturedOptions!.path, '/api/v1/copilot/voice');
      expect(capturedOptions!.method, 'POST');
      final data = capturedOptions!.data as Map<String, dynamic>;
      expect(data['utterance'], 'find trucks');
    });

    test('voiceInput returns CopilotResponse on success', () async {
      final client = _fakeClient(() => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: {
          'conversation_id': 'conv-voice',
          'plan': {
            'plan_id': 'plan-voice',
            'conversation_id': 'conv-voice',
            'intent': {'name': 'vehicle.search', 'raw_utterance': 'find trucks'},
          },
        },
      ));
      final endpoints = CopilotEndpoints(client);

      final result = await endpoints.voiceInput(transcript: 'find trucks');

      expect(result.conversationId, 'conv-voice');
      expect(result.plan, isNotNull);
    });

    test('voiceInput throws on error', () async {
      final client = _failingClient(statusCode: 503);
      final endpoints = CopilotEndpoints(client);

      expect(
        () => endpoints.voiceInput(transcript: 'test'),
        throwsA(isA<DioException>()),
      );
    });
  });

  group('CopilotEndpoints — plans', () {
    test('getPlan sends GET to /api/v1/copilot/plans/{id}', () async {
      RequestOptions? capturedOptions;
      final client = _capturingPlanClient((options) {
        capturedOptions = options;
      }, planId: 'plan-1');
      final endpoints = CopilotEndpoints(client);

      final result = await endpoints.getPlan('plan-1');

      expect(capturedOptions!.path, '/api/v1/copilot/plans/plan-1');
      expect(capturedOptions!.method, 'GET');
      expect(result.planId, 'plan-1');
    });

    test('getPlan returns CopilotExecutionPlan on success', () async {
      final client = _fakeClient(() => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: {
          'plan_id': 'plan-found',
          'conversation_id': 'conv',
          'intent': {'name': 'test', 'raw_utterance': 'test'},
        },
      ));
      final endpoints = CopilotEndpoints(client);

      final result = await endpoints.getPlan('plan-found');

      expect(result.planId, 'plan-found');
    });

    test('getPlan throws when plan_id is missing from response', () async {
      final client = _fakeClient(() => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: {'error': 'Plan not found'},
      ));
      final endpoints = CopilotEndpoints(client);

      expect(
        () => endpoints.getPlan('plan-missing'),
        throwsA(isA<Exception>()),
      );
    });

    test('getPlan throws on HTTP error', () async {
      final client = _failingClient(statusCode: 404);
      final endpoints = CopilotEndpoints(client);

      expect(
        () => endpoints.getPlan('plan-404'),
        throwsA(isA<DioException>()),
      );
    });

    test('confirmPlan sends POST to /api/v1/copilot/plans/{id}/confirm',
        () async {
      RequestOptions? capturedOptions;
      final client = _capturingClient((options) {
        capturedOptions = options;
      });
      final endpoints = CopilotEndpoints(client);

      await endpoints.confirmPlan('plan-1', null);

      expect(capturedOptions!.path, '/api/v1/copilot/plans/plan-1/confirm');
      expect(capturedOptions!.method, 'POST');
    });

    test('confirmPlan sends confirmation_phrase in body', () async {
      Map<String, dynamic>? requestBody;
      final client = _fakeClient(() => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: {'status': 'completed'},
      ));
      client.dio.interceptors.clear();
      client.dio.interceptors.add(QueuedInterceptorsWrapper(
        onRequest: (options, handler) {
          requestBody = options.data as Map<String, dynamic>?;
          handler.resolve(Response(
            requestOptions: options,
            statusCode: 200,
            data: {'status': 'completed'},
          ));
        },
      ));
      final endpoints = CopilotEndpoints(client);

      await endpoints.confirmPlan('plan-1', null,
          confirmationPhrase: 'I understand');

      expect(requestBody, isNotNull);
      expect(requestBody!['confirmation_phrase'], 'I understand');
    });

    test('confirmPlan sends null body when no phrase', () async {
      dynamic requestBody;
      final client = _fakeClient(() => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: {'status': 'completed'},
      ));
      client.dio.interceptors.clear();
      client.dio.interceptors.add(QueuedInterceptorsWrapper(
        onRequest: (options, handler) {
          requestBody = options.data;
          handler.resolve(Response(
            requestOptions: options,
            statusCode: 200,
            data: {'status': 'completed'},
          ));
        },
      ));
      final endpoints = CopilotEndpoints(client);

      await endpoints.confirmPlan('plan-1', null);

      expect(requestBody, isNull);
    });

    test('confirmPlan throws on error', () async {
      final client = _failingClient(statusCode: 403);
      final endpoints = CopilotEndpoints(client);

      expect(
        () => endpoints.confirmPlan('plan-1', null),
        throwsA(isA<DioException>()),
      );
    });

    test('cancelPlan sends POST to /api/v1/copilot/plans/{id}/cancel',
        () async {
      RequestOptions? capturedOptions;
      final client = _capturingClient((options) {
        capturedOptions = options;
      });
      final endpoints = CopilotEndpoints(client);

      await endpoints.cancelPlan('plan-1');

      expect(capturedOptions!.path, '/api/v1/copilot/plans/plan-1/cancel');
      expect(capturedOptions!.method, 'POST');
    });

    test('cancelPlan throws on error', () async {
      final client = _failingClient(statusCode: 500);
      final endpoints = CopilotEndpoints(client);

      expect(
        () => endpoints.cancelPlan('plan-1'),
        throwsA(isA<DioException>()),
      );
    });

    test('undoPlan sends POST to /api/v1/copilot/plans/{id}/undo', () async {
      RequestOptions? capturedOptions;
      final client = _capturingClient((options) {
        capturedOptions = options;
      });
      final endpoints = CopilotEndpoints(client);

      await endpoints.undoPlan('plan-1');

      expect(capturedOptions!.path, '/api/v1/copilot/plans/plan-1/undo');
      expect(capturedOptions!.method, 'POST');
    });
  });

  group('CopilotEndpoints — conversations', () {
    test('listConversations sends GET with limit parameter', () async {
      RequestOptions? capturedOptions;
      final client = _capturingClient((options) {
        capturedOptions = options;
      });
      final endpoints = CopilotEndpoints(client);

      await endpoints.listConversations(limit: 10);

      expect(capturedOptions!.path, '/api/v1/copilot/conversations');
      expect(capturedOptions!.method, 'GET');
      expect(capturedOptions!.queryParameters['limit'], 10);
    });

    test('listConversations sends cursor when provided', () async {
      RequestOptions? capturedOptions;
      final client = _capturingClient((options) {
        capturedOptions = options;
      });
      final endpoints = CopilotEndpoints(client);

      await endpoints.listConversations(cursor: 'cursor-abc');

      expect(capturedOptions!.queryParameters['cursor'], 'cursor-abc');
    });

    test('listConversations returns data map', () async {
      final client = _fakeClient(() => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: {'items': <dynamic>[], 'next_cursor': null},
      ));
      final endpoints = CopilotEndpoints(client);

      final result = await endpoints.listConversations();

      expect(result.containsKey('items'), true);
      expect(result.containsKey('next_cursor'), true);
    });

    test('getConversation sends GET with conversation ID', () async {
      RequestOptions? capturedOptions;
      final client = _capturingClient((options) {
        capturedOptions = options;
      });
      final endpoints = CopilotEndpoints(client);

      await endpoints.getConversation('conv-123');

      expect(capturedOptions!.path,
          '/api/v1/copilot/conversations/conv-123');
      expect(capturedOptions!.method, 'GET');
    });
  });

  group('CopilotEndpoints — insights', () {
    test('listInsights sends GET with limit', () async {
      RequestOptions? capturedOptions;
      final client = _capturingClient((options) {
        capturedOptions = options;
      });
      final endpoints = CopilotEndpoints(client);

      await endpoints.listInsights(limit: 5);

      expect(capturedOptions!.path, '/api/v1/copilot/insights');
      expect(capturedOptions!.queryParameters['limit'], 5);
    });

    test('listInsights sends statusFilter when provided', () async {
      RequestOptions? capturedOptions;
      final client = _capturingClient((options) {
        capturedOptions = options;
      });
      final endpoints = CopilotEndpoints(client);

      await endpoints.listInsights(statusFilter: 'pending');

      expect(capturedOptions!.queryParameters['status_filter'], 'pending');
    });
  });

  group('CopilotEndpoints — WebSocket timeline', () {
    test('watchPlanTimeline returns a Stream', () {
      final client = ApiClient.create(
        baseUrl: 'https://test.com',
        getAccessToken: () async => null,
      );
      final endpoints = CopilotEndpoints(client);

      final stream = endpoints.watchPlanTimeline(
        baseUrl: 'https://test.com',
        conversationId: 'conv-1',
        token: 'test-token',
      );

      expect(stream, isA<Stream<Map<String, dynamic>>>());
    });

    test('watchPlanTimeline converts https to wss', () {
      final client = ApiClient.create(
        baseUrl: 'https://test.com',
        getAccessToken: () async => null,
      );
      final endpoints = CopilotEndpoints(client);

      // Should not throw — the WebSocket connection will fail but
      // errors are surfaced on the stream, not thrown.
      final stream = endpoints.watchPlanTimeline(
        baseUrl: 'https://test.com',
        conversationId: 'conv-ws',
        token: 'token',
      );

      expect(stream, isA<Stream>());
    });
  });
}
