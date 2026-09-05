import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/core/sync/delta_sync_service.dart';
import 'package:operion_mobile/core/sync/sync_providers.dart';
import 'package:operion_mobile/features/driver/messages/message_list_screen.dart';
import 'package:operion_mobile/features/driver/messages/message_providers.dart';
import 'package:operion_mobile/shared/models/message.dart';

// ---------------------------------------------------------------------------
// Fake SyncCoordinator — records entity sync calls.
// ---------------------------------------------------------------------------

class FakeSyncCoordinator implements SyncCoordinator {
  final List<String> entityCalls = [];

  @override
  Future<void>? get activeRun => null;

  @override
  Future<void> runNow() async {}

  @override
  Future<SyncResult> syncEntity(String entityType) async {
    entityCalls.add(entityType);
    return SyncResult(success: true, recordsSynced: 0);
  }
}

// ---------------------------------------------------------------------------
// Test helper
// ---------------------------------------------------------------------------

Widget _wrapMessageList({
  required List<Message> messages,
  required FakeSyncCoordinator fakeCoordinator,
}) {
  return ProviderScope(
    overrides: [
      messagesProvider.overrideWith((ref) async => messages),
      syncCoordinatorProvider.overrideWith((ref) => fakeCoordinator),
      syncStatusProvider.overrideWith((ref) => SyncStatus.idle),
      syncErrorMessageProvider.overrideWith((ref) => null),
      syncRecordsCountProvider.overrideWith((ref) => 0),
      syncCursorsProvider.overrideWith((ref) => const {}),
      lastSyncAtProvider.overrideWith((ref) => null),
    ],
    child: const MaterialApp(
      localizationsDelegates: [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: MessageListScreen(),
    ),
  );
}

void main() {
  group('MessageListScreen — empty state refresh (F2)', () {
    testWidgets('empty state is wrapped in RefreshIndicator and pull-to-refresh triggers sync',
        (tester) async {
      final fakeCoordinator = FakeSyncCoordinator();

      await tester.pumpWidget(_wrapMessageList(
        messages: [],
        fakeCoordinator: fakeCoordinator,
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Empty state visible
      expect(find.text('No messages'), findsOneWidget);

      // Pull-to-refresh on the empty state (scrollable must allow overscroll)
      await tester.fling(
        find.byType(RefreshIndicator),
        const Offset(0, 300),
        1000,
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));

      // Assert syncEntity('message') was called via the onRefresh path
      expect(fakeCoordinator.entityCalls, contains('message'));
    });
  });
}
