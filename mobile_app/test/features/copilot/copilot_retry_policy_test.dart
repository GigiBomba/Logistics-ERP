import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/features/copilot/network/copilot_retry_policy.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

DioException _dioError(DioExceptionType type, {int? status}) => DioException(
      requestOptions: RequestOptions(path: '/api/v1/copilot/chat'),
      type: type,
      response: status != null
          ? Response(
              requestOptions: RequestOptions(path: '/api/v1/copilot/chat'),
              statusCode: status,
              data: <String, dynamic>{'error': 'x'},
            )
          : null,
    );

DioException _serverError(RequestOptions options, int status) =>
    DioException.badResponse(
      statusCode: status,
      requestOptions: options,
      response: Response(requestOptions: options, statusCode: status),
    );

/// Scripted [HttpClientAdapter] that throws the configured failures first and
/// then serves a 200 response. Mirrors the real-world error path (raw
/// [DioException]s thrown from the transport), so the retry interceptor sees
/// exactly what it sees in production.
class _ScriptedAdapter implements HttpClientAdapter {
  int attempts = 0;
  final List<DioException Function(RequestOptions options)> failures;

  _ScriptedAdapter(this.failures);

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    attempts++;
    if (attempts <= failures.length) {
      throw failures[attempts - 1](options);
    }
    return ResponseBody.fromString(
      '{"ok": true}',
      200,
      headers: <String, List<String>>{
        Headers.contentTypeHeader: <String>[Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

typedef _RetryClientResult = ({ApiClient client, _ScriptedAdapter adapter});

/// Builds an [ApiClient] wired with the retry interceptor and a scripted
/// transport adapter.
_RetryClientResult _retryClient({
  required CopilotRetryPolicy policy,
  required List<DioException Function(RequestOptions options)> failures,
}) {
  final client = ApiClient.create(
    baseUrl: 'https://test.com',
    getAccessToken: () async => null,
  );
  client.dio.interceptors.clear();
  client.dio.interceptors.add(CopilotRetryInterceptor(
    dio: client.dio,
    policy: policy,
  ));
  final adapter = _ScriptedAdapter(failures);
  client.dio.httpClientAdapter = adapter;
  return (client: client, adapter: adapter);
}

void main() {
  // ==========================================================================
  // §28.1 error classification
  // ==========================================================================
  group('isTransientDioError (§28.1)', () {
    test('timeouts and connection errors are transient', () {
      expect(
        isTransientDioError(_dioError(DioExceptionType.connectionTimeout)),
        isTrue,
      );
      expect(
        isTransientDioError(_dioError(DioExceptionType.sendTimeout)),
        isTrue,
      );
      expect(
        isTransientDioError(_dioError(DioExceptionType.receiveTimeout)),
        isTrue,
      );
      expect(
        isTransientDioError(_dioError(DioExceptionType.connectionError)),
        isTrue,
      );
    });

    test('5xx responses and 429 rate limits are transient', () {
      expect(
        isTransientDioError(_dioError(DioExceptionType.badResponse, status: 500)),
        isTrue,
      );
      expect(
        isTransientDioError(_dioError(DioExceptionType.badResponse, status: 503)),
        isTrue,
      );
      expect(
        isTransientDioError(_dioError(DioExceptionType.badResponse, status: 429)),
        isTrue,
      );
    });

    test('deterministic 4xx errors are never retried', () {
      expect(
        isTransientDioError(_dioError(DioExceptionType.badResponse, status: 400)),
        isFalse,
      );
      expect(
        isTransientDioError(_dioError(DioExceptionType.badResponse, status: 403)),
        isFalse,
      );
      expect(
        isTransientDioError(_dioError(DioExceptionType.badResponse, status: 404)),
        isFalse,
      );
      expect(
        isTransientDioError(_dioError(DioExceptionType.badResponse, status: 409)),
        isFalse,
      );
    });

    test('cancellation and bad certificates are never retried', () {
      expect(isTransientDioError(_dioError(DioExceptionType.cancel)), isFalse);
      expect(
        isTransientDioError(_dioError(DioExceptionType.badCertificate)),
        isFalse,
      );
    });
  });

  // ==========================================================================
  // CopilotRetryPolicy
  // ==========================================================================
  group('CopilotRetryPolicy', () {
    test('maxRetries defaults to exactly one (§28.1)', () {
      expect(const CopilotRetryPolicy().maxRetries, 1);
    });

    test('backoff is exponential and capped at maxBackoff', () {
      const policy = CopilotRetryPolicy(
        baseBackoff: Duration(seconds: 1),
        maxBackoff: Duration(seconds: 5),
      );
      expect(policy.backoff(1), const Duration(seconds: 1));
      expect(policy.backoff(2), const Duration(seconds: 2));
      expect(policy.backoff(3), const Duration(seconds: 4));
      expect(policy.backoff(4), const Duration(seconds: 5)); // capped
      expect(policy.backoff(10), const Duration(seconds: 5));
    });

    test('shouldRetry delegates to isTransientDioError', () {
      const policy = CopilotRetryPolicy();
      expect(
        policy.shouldRetry(_dioError(DioExceptionType.connectionError)),
        isTrue,
      );
      expect(
        policy.shouldRetry(_dioError(DioExceptionType.badResponse, status: 400)),
        isFalse,
      );
    });
  });

  // ==========================================================================
  // CopilotRetryInterceptor — behaviour
  // ==========================================================================
  group('CopilotRetryInterceptor', () {
    test('retries a transient connection error once, then succeeds', () async {
      final result = _retryClient(
        policy: const CopilotRetryPolicy(
          baseBackoff: Duration(milliseconds: 1),
        ),
        failures: <DioException Function(RequestOptions)>[
          (options) => DioException.connectionError(
                requestOptions: options,
                reason: 'connection reset',
              ),
        ],
      );

      final response = await result.client.get('/api/v1/copilot/chat');

      expect(result.adapter.attempts, 2);
      expect(response.statusCode, 200);
    });

    test('retries a transient 5xx once, then succeeds', () async {
      final result = _retryClient(
        policy: const CopilotRetryPolicy(
          baseBackoff: Duration(milliseconds: 1),
        ),
        failures: <DioException Function(RequestOptions)>[
          (options) => _serverError(options, 500),
        ],
      );

      final response = await result.client.get('/api/v1/copilot/chat');

      expect(result.adapter.attempts, 2);
      expect(response.statusCode, 200);
    });

    test('never retries deterministic 4xx errors', () async {
      final result = _retryClient(
        // Generous cap to prove even a high allowance does not trigger a retry.
        policy: const CopilotRetryPolicy(maxRetries: 3),
        failures: <DioException Function(RequestOptions)>[
          (options) => _serverError(options, 403),
        ],
      );

      await expectLater(
        result.client.get('/api/v1/copilot/chat'),
        throwsA(isA<DioException>()),
      );
      expect(result.adapter.attempts, 1);
    });

    test('stops after maxRetries and propagates the error', () async {
      final result = _retryClient(
        policy: const CopilotRetryPolicy(
          maxRetries: 1,
          baseBackoff: Duration(milliseconds: 1),
        ),
        failures: <DioException Function(RequestOptions)>[
          (options) => _serverError(options, 500),
          (options) => _serverError(options, 500),
        ],
      );

      await expectLater(
        result.client.get('/api/v1/copilot/chat'),
        throwsA(isA<DioException>()),
      );
      expect(result.adapter.attempts, 2);
    });

    test('applies a backoff delay before retrying', () async {
      final stopwatch = Stopwatch()..start();
      final result = _retryClient(
        policy: const CopilotRetryPolicy(
          maxRetries: 1,
          baseBackoff: Duration(milliseconds: 50),
        ),
        failures: <DioException Function(RequestOptions)>[
          (options) => DioException.connectionError(
                requestOptions: options,
                reason: 'connection reset',
              ),
        ],
      );

      await result.client.get('/api/v1/copilot/chat');
      stopwatch.stop();

      expect(result.adapter.attempts, 2);
      // The retry must wait at least the configured base backoff (50 ms),
      // proving a delay is actually applied.
      expect(
        stopwatch.elapsed,
        greaterThanOrEqualTo(const Duration(milliseconds: 40)),
      );
    });
  });
}