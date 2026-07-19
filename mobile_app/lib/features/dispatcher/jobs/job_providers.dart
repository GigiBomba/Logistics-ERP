import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../home/dispatcher_providers.dart';

/// Fetches a single job by [jobId] from the cached jobs list.
///
/// Since [DispatcherEndpoints] does not expose a `getJob(id)` endpoint, this
/// provider reads from [dispatcherJobsProvider] and filters locally.
///
/// Returns an empty map when the job is not found; callers should handle
/// missing data gracefully.
final jobDetailProvider =
    FutureProvider.family<Map<String, dynamic>, int>((ref, jobId) async {
  final jobs = ref.watch(dispatcherJobsProvider).value;
  if (jobs == null) {
    return (await ref.read(dispatcherJobsProvider.future)).firstWhere(
      (j) {
        final id = j['id'];
        if (id is int) return id == jobId;
        if (id is String) return int.tryParse(id) == jobId;
        return false;
      },
      orElse: () => <String, dynamic>{},
    );
  }
  return jobs.firstWhere(
    (j) {
      final id = j['id'];
      if (id is int) return id == jobId;
      if (id is String) return int.tryParse(id) == jobId;
      return false;
    },
    orElse: () => <String, dynamic>{},
  );
});

/// Tracks whether a reassign API call is currently in-flight.
///
/// Set to `true` while [DispatcherEndpoints.reassignTransport] is executing
/// and reset to `false` on completion (success or error).
final reassigningProvider = StateProvider<bool>((ref) => false);
