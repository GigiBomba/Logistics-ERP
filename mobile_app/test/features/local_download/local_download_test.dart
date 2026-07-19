import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/local_download/screens/local_download_screen.dart';

/// Helper: wraps [child] in MaterialApp with localisations so that
/// `context.loc` works.
Widget wrapLocalDownload() {
  return MaterialApp(
    localizationsDelegates: const [
      AppLocalizations.delegate,
      DefaultMaterialLocalizations.delegate,
      DefaultWidgetsLocalizations.delegate,
    ],
    supportedLocales: AppLocalizations.supportedLocales,
    home: const LocalDownloadScreen(),
  );
}

void main() {
  // ==========================================================================
  // Initial state
  // ==========================================================================
  group('LocalDownloadScreen — initial state', () {
    testWidgets('renders app bar with title', (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pumpAndSettle();

      expect(find.text('Local Download'), findsOneWidget);
    });

    testWidgets('shows select category prompt', (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pumpAndSettle();

      expect(find.text('Select Category'), findsOneWidget);
    });

    testWidgets('renders all five category cards', (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pumpAndSettle();

      expect(find.text('Documents'), findsAtLeastNWidgets(1));
      expect(find.text('Invoices'), findsOneWidget);
      expect(find.text('Receipts'), findsOneWidget);
      expect(find.text('OCR Results'), findsOneWidget);
      expect(find.text('Trip History'), findsOneWidget);
    });

    testWidgets('download button is not shown when no category selected',
        (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pumpAndSettle();

      expect(find.text('Download'), findsNothing);
    });
  });

  // ==========================================================================
  // Category selection
  // ==========================================================================
  group('LocalDownloadScreen — category selection', () {
    testWidgets('selecting a category shows Lucide check icon',
        (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Invoices'));
      await tester.pumpAndSettle();

      // The check icon from LucideIcons
      expect(find.byIcon(LucideIcons.check), findsOneWidget);
    });

    testWidgets('selecting a category shows download button', (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Receipts'));
      await tester.pumpAndSettle();

      expect(find.text('Download'), findsOneWidget);
    });

    testWidgets('changing selected category still shows check icon',
        (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Documents'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Trip History'));
      await tester.pumpAndSettle();

      // Check icon shown on the newly selected category
      expect(find.byIcon(LucideIcons.check), findsOneWidget);
    });
  });

  // ==========================================================================
  // Download action
  // ==========================================================================
  group('LocalDownloadScreen — download action', () {
    testWidgets('tapping download shows snackbar', (tester) async {
      await tester.pumpWidget(wrapLocalDownload());
      await tester.pumpAndSettle();

      await tester.tap(find.text('OCR Results'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Download'));
      await tester.pumpAndSettle();

      expect(find.text('Downloading...'), findsOneWidget);
    });
  });
}
