import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/models/message.dart';
import '../home/driver_providers.dart';

/// Fetches all messages for the current driver from the API.
///
/// Returns a list of [Message] objects parsed from the JSON response.
/// Widgets should handle loading, error, and empty states via
/// [AsyncValue.when].
final messagesProvider = FutureProvider<List<Message>>((ref) async {
  final endpoints = ref.watch(driverEndpointsProvider);
  final response = await endpoints.getMessages();
  final raw = response.data;
  final list = raw is List ? raw : (raw is Map ? (raw['records'] ?? raw['data'] ?? []) as List : []);
  return list
      .map((json) => Message.fromJson(json as Map<String, dynamic>))
      .toList();
});

/// Tracks whether a message send operation is currently in flight.
///
/// Widgets can watch this provider to show a sending indicator on the
/// send button or input field.
final messageSendingProvider = StateProvider<bool>((ref) => false);
