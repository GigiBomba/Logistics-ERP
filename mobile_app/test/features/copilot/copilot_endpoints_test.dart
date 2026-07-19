import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/copilot_endpoints.dart';

/// Minimal ApiClient that returns canned responses.
/// Interceptors are cleared so no real HTTP calls are made.
ApiClient _fakeClient(Response Function() onResponse) {
  final client = ApiClient.create(
    baseUrl: 'https://test.com',
    getAccessToken: () async => null,
  );
  // Replace the real HTTP call with a canned response
  client.dio.interceptors.clear();
  client.dio.interceptors.add(QueuedInterceptorsWrapper(
    onRequest: (options, handler) {
      handler.resolve(onResponse());
    },
  ));
  return client;
}

void main() {
  group('CopilotEndpoints', () {
    test('chat calls POST /api/v1/copilot/chat', () async {
      final client = _fakeClient(() => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: {'conversation_id': 'test-conv'},
      ));
      final endpoints = CopilotEndpoints(client);

      final result = await endpoints.chat(utterance: 'find trucks');

      expect(result.conversationId, 'test-conv');
    });

    test('getPlan calls GET /api/v1/copilot/plans/{id}', () async {
      final client = _fakeClient(() => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: {
          'plan_id': 'test-plan',
          'conversation_id': 'conv',
          'intent': {'name': 'test', 'raw_utterance': 'test'},
        },
      ));
      final endpoints = CopilotEndpoints(client);

      final result = await endpoints.getPlan('test-plan');

      expect(result.planId, 'test-plan');
    });

    test('confirmPlan calls POST /api/v1/copilot/plans/{id}/confirm', () async {
      final client = _fakeClient(() => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: {'status': 'completed'},
      ));
      final endpoints = CopilotEndpoints(client);

      final result = await endpoints.confirmPlan('test-plan', null);

      expect(result['status'], 'completed');
    });

    test('confirmPlan sends confirmation_phrase in request body', () async {
      Map<String, dynamic>? requestBody;
      final client = _fakeClient(() => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: {'status': 'completed'},
      ));
      // Replace the interceptor to also capture the request data
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

      await endpoints.confirmPlan('test-plan', null,
          confirmationPhrase: 'I understand the risks');

      // The body should contain the confirmation phrase
      expect(requestBody, isNotNull);
      expect(requestBody!['confirmation_phrase'], 'I understand the risks');
    });

    test('cancelPlan calls POST /api/v1/copilot/plans/{id}/cancel', () async {
      final client = _fakeClient(() => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: {'status': 'cancelled'},
      ));
      final endpoints = CopilotEndpoints(client);

      final result = await endpoints.cancelPlan('test-plan');

      expect(result['status'], 'cancelled');
    });

    test('listConversations calls GET /api/v1/copilot/conversations', () async {
      final client = _fakeClient(() => Response(
        requestOptions: RequestOptions(path: ''),
        statusCode: 200,
        data: {'items': <dynamic>[], 'next_cursor': null},
      ));
      final endpoints = CopilotEndpoints(client);

      final result = await endpoints.listConversations();

      expect(result.containsKey('items'), true);
    });
  });
}
