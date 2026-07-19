import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Provides a tick stream that emits every second while the app is active.
/// Used to refresh the elapsed-time display on the trip overview.
final elapsedTimerProvider = StreamProvider<void>((ref) {
  return Stream.periodic(const Duration(seconds: 1), (_) => null);
});
