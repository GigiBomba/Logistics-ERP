import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/document_center/screens/document_center_screen.dart';

/// Helper: wraps [child] in MaterialApp with localisations so that
/// `context.loc` works.
Widget wrapDocumentCenter() {
  return MaterialApp(
    localizationsDelegates: const [
      AppLocalizations.delegate,
      DefaultMaterialLocalizations.delegate,
      DefaultWidgetsLocalizations.delegate,
    ],
    supportedLocales: AppLocalizations.supportedLocales,
    home: const DocumentCenterScreen(),
  );
}

void main() {
  // ==========================================================================
  // Initial state — tab bar rendering
  // ==========================================================================
  group('DocumentCenterScreen — initial state', () {
    testWidgets('renders app bar with title', (tester) async {
      await tester.pumpWidget(wrapDocumentCenter());
      await tester.pumpAndSettle();

      expect(find.text('Document Center'), findsOneWidget);
    });

    testWidgets('renders two tabs: Documents and Automation', (tester) async {
      await tester.pumpWidget(wrapDocumentCenter());
      await tester.pumpAndSettle();

      // Tab labels appear — both Documents tab label and the empty-state title
      // use the same key so findsAtLeast is safe
      expect(find.text('Documents'), findsAtLeastNWidgets(1));
      expect(find.text('Automation'), findsOneWidget);
    });

    testWidgets('shows folder open icon on Documents tab', (tester) async {
      await tester.pumpWidget(wrapDocumentCenter());
      await tester.pumpAndSettle();

      expect(find.byIcon(LucideIcons.folderOpen), findsOneWidget);
    });

    testWidgets('shows camera icon on Automation tab', (tester) async {
      await tester.pumpWidget(wrapDocumentCenter());
      await tester.pumpAndSettle();

      expect(find.byIcon(LucideIcons.camera), findsOneWidget);
    });
  });

  // ==========================================================================
  // Documents tab (default, first tab)
  // ==========================================================================
  group('DocumentCenterScreen — Documents tab', () {
    testWidgets('shows file text icon in documents tab', (tester) async {
      await tester.pumpWidget(wrapDocumentCenter());
      await tester.pumpAndSettle();

      // fileText icon appears as the empty-state icon when no documents
      expect(find.byIcon(LucideIcons.fileText), findsOneWidget);
    });
  });

  // ==========================================================================
  // Automation tab
  // ==========================================================================
  group('DocumentCenterScreen — Automation tab', () {
    testWidgets('switching to Automation tab shows OCR content',
        (tester) async {
      await tester.pumpWidget(wrapDocumentCenter());
      await tester.pumpAndSettle();

      // Tap Automation tab
      await tester.tap(find.text('Automation'));
      await tester.pumpAndSettle();

      expect(find.text('OCR Document Capture'), findsOneWidget);
      expect(
        find.text(
            'Capture a document photo to automatically extract fields.'),
        findsOneWidget,
      );
    });

    testWidgets('shows Capture Photo button on Automation tab',
        (tester) async {
      await tester.pumpWidget(wrapDocumentCenter());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Automation'));
      await tester.pumpAndSettle();

      expect(find.text('Capture Photo'), findsOneWidget);
    });

    testWidgets('tapping Capture Photo shows snackbar', (tester) async {
      await tester.pumpWidget(wrapDocumentCenter());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Automation'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Capture Photo'));
      await tester.pumpAndSettle();

      expect(find.text('Upload confirmed, processing...'), findsOneWidget);
    });
  });

  // ==========================================================================
  // Tab switching
  // ==========================================================================
  group('DocumentCenterScreen — tab switching', () {
    testWidgets('switching back to Documents tab shows file icon',
        (tester) async {
      await tester.pumpWidget(wrapDocumentCenter());
      await tester.pumpAndSettle();

      // Go to Automation
      await tester.tap(find.text('Automation'));
      await tester.pumpAndSettle();

      // Switch back to Documents
      await tester.tap(find.text('Documents'));
      await tester.pumpAndSettle();

      expect(find.byIcon(LucideIcons.fileText), findsOneWidget);
    });
  });
}
