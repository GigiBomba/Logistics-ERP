/// Co-Pilot retry policy mirroring the backend's §28.1 error policy.
///
/// §28.1 (Tool execution errors):
/// - Exactly **one** automatic retry for errors classified as *transient*
///   (timeouts, connection resets, 5xx).
/// - **Never** retried for *deterministic* errors (4xx validation /
///   permission / freshness / concurrency — the same input fails the same
///   way), request cancellations, or certificate failures.
///
/// Backoff follows the same exponential schedule the backend uses for its own
/// service calls (§28.1, §23.3): `baseBackoff * 2^(attempt-1)`, capped at
/// [CopilotRetryPolicy.maxBackoff].
library;

import 'package:dio/dio.dart';

/// Classifies a [DioException] as *transient* (safe to retry once) or
/// *deterministic* (never retried, per §28.1).
///
/// Transient:
/// - connect / send / receive / transform timeouts,
/// - connection errors and socket resets (no server response),
/// - 5xx responses, and 429 rate limits (the backend retries rate limits on
///   LLM-provider errors, §23.2 / §28.1).
///
/// Deterministic:
/// - any 4xx response (validation, permission, freshness, not found, ...),
/// - request cancellation,
/// - bad certificates (trust posture does not improve by retrying).
bool isTransientDioError(DioException error) {
  switch (error.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
    case DioExceptionType.transformTimeout:
    case DioExceptionType.connectionError:
      return true;
    case DioExceptionType.badResponse:
      final status = error.response?.statusCode;
      return status != null && (status >= 500 || status == 429);
    case DioExceptionType.unknown:
      // No response body → the server never answered (e.g. a socket reset
      // surfaced as `unknown`). With a response, fall through to the status.
      if (error.response == null) return true;
      final status = error.response!.statusCode ?? 0;
      return status >= 500 || status == 429;
    case DioExceptionType.cancel:
    case DioExceptionType.badCertificate:
      return false;
  }
}

/// Retry schedule for Co-Pilot API calls (§28.1).
class CopilotRetryPolicy {
  /// Maximum automatic retries per request. §28.1 mandates exactly one.
  final int maxRetries;

  /// Base delay for the first retry; doubles on each further attempt.
  final Duration baseBackoff;

  /// Upper bound on any single backoff delay.
  final Duration maxBackoff;

  const CopilotRetryPolicy({
    this.maxRetries = 1,
    this.baseBackoff = const Duration(milliseconds: 300),
    this.maxBackoff = const Duration(seconds: 3),
  });

  /// Whether [error] is eligible for an automatic retry.
  bool shouldRetry(DioException error) => isTransientDioError(error);

  /// Exponential backoff delay before the [attempt]-th retry (1-based):
  /// `baseBackoff * 2^(attempt-1)`, capped at [maxBackoff].
  Duration backoff(int attempt) {
    if (attempt < 1) attempt = 1;
    final multiplier = 1 << (attempt - 1);
    final computed = baseBackoff * multiplier;
    return computed > maxBackoff ? maxBackoff : computed;
  }
}

/// Dio interceptor that applies [CopilotRetryPolicy] to Co-Pilot requests.
///
/// Tracks the attempt count per request in `RequestOptions.extra`
/// (`copilot_retry_attempt`). On a transient failure it waits
/// [CopilotRetryPolicy.backoff] and re-dispatches the *same* request through
/// the same [Dio] instance, so the full interceptor chain (auth headers,
/// logging) applies to the retry exactly as it did to the original attempt.
///
/// This is deliberately a plain [Interceptor], not a [QueuedInterceptor]:
/// the re-entrant `dio.fetch` from inside `onError` must not wait behind the
/// error-queue slot held by the failing attempt (which would deadlock).
class CopilotRetryInterceptor extends Interceptor {
  /// `RequestOptions.extra` key used to track retries per request.
  static const String retryAttemptKey = 'copilot_retry_attempt';

  /// The [Dio] instance used to re-dispatch retried requests so the full
  /// interceptor chain applies again.
  final Dio dio;

  /// The retry schedule applied to each failed request.
  final CopilotRetryPolicy policy;

  CopilotRetryInterceptor({
    required this.dio,
    this.policy = const CopilotRetryPolicy(),
  });

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final attempts = err.requestOptions.extra[retryAttemptKey] as int? ?? 0;
    if (attempts >= policy.maxRetries || !policy.shouldRetry(err)) {
      return handler.next(err);
    }

    final nextAttempt = attempts + 1;
    err.requestOptions.extra[retryAttemptKey] = nextAttempt;
    await Future<void>.delayed(policy.backoff(nextAttempt));

    try {
      final response = await dio.fetch(err.requestOptions);
      return handler.resolve(response);
    } catch (retryError) {
      return handler.next(retryError is DioException ? retryError : err);
    }
  }
}