import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/core/storage/local_db.dart';
import 'package:operion_mobile/core/sync/action_queue.dart';
import 'package:operion_mobile/core/sync/sync_providers.dart';
import 'package:operion_mobile/features/local_download/screens/local_download_screen.dart';

// ---------------------------------------------------------------------------
// Fake LocalDatabase for tests
// ---------------------------------------------------------------------------

class _FakeLocalDatabase implements LocalDatabase {
  final _collections = <String, List<Map<String, dynamic>>>{};

  void setRecords(String collection, List<Map<String, dynamic>> records) {
    _collections[collection] = records;
  }

  @override
  Future<void> initialize() async {}

  @override
  Future<dynamic> read(String key, {String namespace = 'default'}) async => null;

  @override
  Future<void> write(String key, dynamic value, {String namespace = 'default'}) async {}

  @override
  Future<void> delete(String key, {String namespace = 'default'}) async {}

  @override
  Future<List<String>> keysWithPrefix(String prefix, {String namespace = 'default'}) async => [];

  @override
  Future<void> deleteAllWithPrefix(String prefix, {String namespace = 'default'}) async {}

  @override
  Future<void> cacheData(String collection, String key, Map<String, dynamic> data) async {}

  @override
  Future<void> cacheMany(String collection, Map<String, Map<String, dynamic>> records) async {}

  @override
  Future<Map<String, dynamic>?> getCachedData(String collection, String key) async => null;

  @override
  Future<List<Map<String, dynamic>>> getAllCachedData(String collection) async {
    return _collections[collection] ?? [];
  }

  @override
  Future<void> cacheTransports(List<Map<String, dynamic>> transports) async {}

  @override
  Future<List<Map<String, dynamic>>> getCachedTransports() async => [];

  @override
  Future<void> clearCollection(String collection) async {}

  @override
  Future<void> close() async {}
}

// ---------------------------------------------------------------------------
// Test helper
// ---------------------------------------------------------------------------

final _fakeDb = _FakeLocalDatabase();

Widget wrapLocalDownload({List<Override> extraOverrides = const []}) {
  return ProviderScope(
    overrides: [
      localDatabaseProvider.overrideWith((ref) async => _fakeDb),
      syncStatusProvider.overrideWith((ref) => SyncStatus.idle),
      syncErrorMessageProvider.overrideWith((ref) => null),
      syncRecordsCountProvider.overrideWith((ref) => 0),
      syncCursorsProvider.overrideWith((ref) => const {}),
      lastSyncAtProvider.overrideWith((ref) => null),
      ...extraOverrides,
    ],
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: MediaQuery(
        data: const MediaQueryData(size: Size(800, 1200)),
        child: const LocalDownloadScreen(),
      ),
    ),
  );
}

void main() {
  // ==========================================================================
  // Initial state
  // ==========================================================================
  group('LocalDownloadScreen — initial state', () {
    testWidgets('renders app bar with title', (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Local Download'), findsOneWidget);
    });

    testWidgets('shows select category prompt', (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Select Category'), findsOneWidget);
    });

    testWidgets('renders all five category cards', (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Documents'), findsAtLeastNWidgets(1));

      // Scroll the ListView to reveal categories lower in the list.
      await tester.scrollUntilVisible(
        find.text('Invoices'),
        100,
        scrollable: find.byType(Scrollable),
      );
      expect(find.text('Invoices'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('Receipts'),
        100,
        scrollable: find.byType(Scrollable),
      );
      expect(find.text('Receipts'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('OCR Results'),
        100,
        scrollable: find.byType(Scrollable),
      );
      expect(find.text('OCR Results'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('Trip History'),
        100,
        scrollable: find.byType(Scrollable),
      );
      expect(find.text('Trip History'), findsOneWidget);
    });

    testWidgets('download button is not shown when no category selected',
        (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Download'), findsNothing);
    });

    testWidgets('renders sync status card', (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // The idle/offline state shows the general_offline label
      expect(find.text('You are offline'), findsOneWidget);
    });

    testWidgets('renders four offline collection cards', (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Transports'), findsOneWidget);
      expect(find.text('Messages'), findsOneWidget);
      expect(find.text('Drivers'), findsOneWidget);
      expect(find.text('Fleet'), findsOneWidget);
    });
  });

  // ==========================================================================
  // Category selection
  // ==========================================================================
  group('LocalDownloadScreen — category selection', () {
    testWidgets('selecting a category shows Lucide check icon',
        (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.scrollUntilVisible(
        find.text('Invoices'),
        100,
        scrollable: find.byType(Scrollable),
      );
      await tester.tap(find.text('Invoices'), warnIfMissed: false);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // The check icon from LucideIcons
      expect(find.byIcon(LucideIcons.check), findsOneWidget);
    });

    testWidgets('selecting a category shows download button', (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.scrollUntilVisible(
        find.text('Receipts'),
        100,
        scrollable: find.byType(Scrollable),
      );
      await tester.tap(find.text('Receipts'), warnIfMissed: false);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Download'), findsOneWidget);
    });

    testWidgets('changing selected category still shows check icon',
        (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.scrollUntilVisible(
        find.text('Documents'),
        100,
        scrollable: find.byType(Scrollable),
      );
      await tester.tap(find.text('Documents'), warnIfMissed: false);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.scrollUntilVisible(
        find.text('Trip History'),
        100,
        scrollable: find.byType(Scrollable),
      );
      await tester.tap(find.text('Trip History'), warnIfMissed: false);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Check icon shown on the newly selected category
      expect(find.byIcon(LucideIcons.check), findsOneWidget);
    });
  });

  // ==========================================================================
  // Download action
  // ==========================================================================
  // ==========================================================================
  // Cached count reactivity (F1)
  // ==========================================================================
  group('LocalDownloadScreen — cached count updates after sync', () {
    testWidgets('counts react to new cached data when syncCursorsProvider changes',
        (tester) async {
      final fakeDb = _FakeLocalDatabase();
      fakeDb.setRecords('transport', List.generate(2, (i) => {'id': i}));

      final container = ProviderContainer(
        overrides: [
          localDatabaseProvider.overrideWith((ref) async => fakeDb),
          syncStatusProvider.overrideWith((ref) => SyncStatus.idle),
          syncErrorMessageProvider.overrideWith((ref) => null),
          syncRecordsCountProvider.overrideWith((ref) => 0),
          syncCursorsProvider.overrideWith((ref) => const {}),
          lastSyncAtProvider.overrideWith((ref) => null),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            localizationsDelegates: [
              AppLocalizations.delegate,
              DefaultMaterialLocalizations.delegate,
              DefaultWidgetsLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: MediaQuery(
              data: MediaQueryData(size: Size(800, 1200)),
              child: LocalDownloadScreen(),
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Initial count for transport
      expect(find.text('2'), findsOneWidget);

      // Simulate a sync run that added more records
      fakeDb.setRecords('transport', List.generate(5, (i) => {'id': i}));
      container.read(syncCursorsProvider.notifier).state = const {'transport': 'cursor-2'};
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // After fix: count updates to 5. Before fix: stays frozen at 2.
      expect(find.text('5'), findsOneWidget);
    });
  });

  // ==========================================================================
  // Download action
  // ==========================================================================
  group('LocalDownloadScreen — download action', () {
    testWidgets('tapping download shows snackbar', (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.scrollUntilVisible(
        find.text('OCR Results'),
        100,
        scrollable: find.byType(Scrollable),
      );
      await tester.tap(find.text('OCR Results'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      await tester.scrollUntilVisible(
        find.text('Download'),
        100,
        scrollable: find.byType(Scrollable),
      );
      // Nudge a little further so the button is fully inside the viewport.
      await tester.drag(find.byType(ListView), const Offset(0, -50));
      await tester.pump();

      await tester.tap(find.text('Download'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));

      expect(find.text('Downloading...'), findsOneWidget);
    });
  });
}
