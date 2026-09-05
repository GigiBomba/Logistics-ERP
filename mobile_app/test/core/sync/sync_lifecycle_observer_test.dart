import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/sync/sync_lifecycle_observer.dart';
import 'package:operion_mobile/core/sync/sync_providers.dart';

void main() {
  group('SyncLifecycleObserver', () {
    Widget buildObserver() {
      return ProviderScope(
        child: MaterialApp(
          home: const SyncLifecycleObserver(
            child: SizedBox.expand(),
          ),
        ),
      );
    }

    testWidgets('reading syncCoordinatorProvider activates listener',
        (tester) async {
      await tester.pumpWidget(buildObserver());
      await tester.pump();

      // The observer should have read syncCoordinatorProvider in initState.
      // We verify the widget mounts without errors.
      expect(find.byType(SyncLifecycleObserver), findsOneWidget);
    });

    testWidgets('does not trigger sync on initial build', (tester) async {
      await tester.pumpWidget(buildObserver());
      await tester.pump();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SyncLifecycleObserver)),
      );
      expect(container.read(syncTriggerProvider), isNull);
    });

    testWidgets('triggers sync on resume when lastSyncAt is null',
        (tester) async {
      await tester.pumpWidget(buildObserver());
      await tester.pump();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SyncLifecycleObserver)),
      );

      // Simulate app resume
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();

      expect(container.read(syncTriggerProvider), isNotNull);
    });

    testWidgets('triggers sync on resume when last sync is older than 5 min',
        (tester) async {
      await tester.pumpWidget(buildObserver());
      await tester.pump();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SyncLifecycleObserver)),
      );

      container.read(lastSyncAtProvider.notifier).state =
          DateTime.now().subtract(const Duration(minutes: 6));

      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();

      expect(container.read(syncTriggerProvider), isNotNull);
    });

    testWidgets('does not trigger sync on resume when last sync is recent',
        (tester) async {
      await tester.pumpWidget(buildObserver());
      await tester.pump();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SyncLifecycleObserver)),
      );

      container.read(lastSyncAtProvider.notifier).state =
          DateTime.now().subtract(const Duration(minutes: 2));

      // Reset trigger so we can detect whether it changes
      container.read(syncTriggerProvider.notifier).state = null;

      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();

      expect(container.read(syncTriggerProvider), isNull);
    });
  });
}
