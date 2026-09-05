import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'sync_providers.dart';

/// Observes app lifecycle changes and triggers a full sync when the app
/// resumes after being in the background for more than 5 minutes (or when
/// no prior sync has been recorded).
///
/// Wrap the root navigator (e.g. [ModeRouter]) with this widget so the
/// observer lives for the entire authenticated session.
class SyncLifecycleObserver extends ConsumerStatefulWidget {
  final Widget child;

  const SyncLifecycleObserver({super.key, required this.child});

  @override
  ConsumerState<SyncLifecycleObserver> createState() =>
      _SyncLifecycleObserverState();
}

class _SyncLifecycleObserverState extends ConsumerState<SyncLifecycleObserver>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // Eagerly read the coordinator so its trigger listener is active.
    ref.read(syncCoordinatorProvider);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      final lastSyncAt = ref.read(lastSyncAtProvider);
      final shouldSync = lastSyncAt == null ||
          DateTime.now().difference(lastSyncAt) > const Duration(minutes: 5);
      if (shouldSync) {
        try {
          ref.read(syncTriggerProvider.notifier).state = DateTime.now();
        } catch (_) {
          // Best-effort — never crash the app on a sync trigger.
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
