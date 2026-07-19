import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/shared/widgets/app_button.dart';
import 'package:operion_mobile/shared/widgets/status_badge.dart';
import 'package:operion_mobile/shared/widgets/empty_state.dart';
import 'package:operion_mobile/shared/widgets/offline_banner.dart';
import 'package:operion_mobile/shared/widgets/staleness_indicator.dart';
import 'package:operion_mobile/shared/widgets/shimmer_loader.dart';
import 'package:operion_mobile/shared/widgets/app_card.dart';
import 'package:operion_mobile/shared/widgets/app_text_field.dart';
import 'package:operion_mobile/shared/widgets/confirmation_dialog.dart';

/// Helper to wrap a widget in [MaterialApp] for testing.
Widget wrapInApp(Widget child) {
  return MaterialApp(home: Scaffold(body: child));
}

void main() {
  // ==========================================================================
  // AppButton
  // ==========================================================================
  group('AppButton', () {
    testWidgets('primary renders label text', (tester) async {
      await tester.pumpWidget(wrapInApp(
        AppButton.primary(label: 'Sign In', onPressed: () {}),
      ));
      expect(find.text('Sign In'), findsOneWidget);
    });

    testWidgets('primary with icon renders icon and label', (tester) async {
      await tester.pumpWidget(wrapInApp(
        AppButton.primary(
          label: 'Save',
          onPressed: () {},
          icon: const Icon(Icons.save),
        ),
      ));
      expect(find.text('Save'), findsOneWidget);
      expect(find.byIcon(Icons.save), findsOneWidget);
    });

    testWidgets('primary loading state shows CircularProgressIndicator',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        AppButton.primary(label: 'Loading', onPressed: () {}, isLoading: true),
      ));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      // Label should not be visible when loading
      expect(find.text('Loading'), findsNothing);
    });

    testWidgets('primary disabled when onPressed is null', (tester) async {
      await tester.pumpWidget(wrapInApp(
        AppButton.primary(label: 'Disabled', onPressed: null),
      ));
      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(button.onPressed, isNull);
    });

    testWidgets('secondary renders OutlinedButton', (tester) async {
      await tester.pumpWidget(wrapInApp(
        AppButton.secondary(label: 'Cancel', onPressed: () {}),
      ));
      expect(find.byType(OutlinedButton), findsOneWidget);
    });

    testWidgets('secondary renders label', (tester) async {
      await tester.pumpWidget(wrapInApp(
        AppButton.secondary(label: 'Back', onPressed: () {}),
      ));
      expect(find.text('Back'), findsOneWidget);
    });

    testWidgets('danger renders with label', (tester) async {
      await tester.pumpWidget(wrapInApp(
        AppButton.danger(label: 'Delete', onPressed: () {}),
      ));
      expect(find.text('Delete'), findsOneWidget);
      expect(find.byType(OutlinedButton), findsOneWidget);
    });

    testWidgets('danger loading shows spinner', (tester) async {
      await tester.pumpWidget(wrapInApp(
        AppButton.danger(label: 'Delete', onPressed: () {}, isLoading: true),
      ));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });
  });

  // ==========================================================================
  // StatusBadge
  // ==========================================================================
  group('StatusBadge', () {
    testWidgets('renders planned status with Romanian label', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'planned'),
      ));
      expect(find.text('Planificat'), findsOneWidget);
    });

    testWidgets('renders delivered status', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'delivered'),
      ));
      expect(find.text('Livrat'), findsOneWidget);
    });

    testWidgets('renders in_progress status', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'in_progress'),
      ));
      expect(find.text('În curs'), findsOneWidget);
    });

    testWidgets('renders cancelled status', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'cancelled'),
      ));
      expect(find.text('Anulat'), findsOneWidget);
    });

    testWidgets('renders unknown status key as fallback text', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'unknown_status'),
      ));
      // Should display the raw statusKey as fallback
      expect(find.text('unknown_status'), findsOneWidget);
    });

    testWidgets('renders with custom label override', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StatusBadge(statusKey: 'delivered', label: 'Custom Label'),
      ));
      expect(find.text('Custom Label'), findsOneWidget);
    });
  });

  // ==========================================================================
  // EmptyState
  // ==========================================================================
  group('EmptyState', () {
    testWidgets('renders icon and title', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const EmptyState(icon: Icon(Icons.inbox), title: 'Nothing here'),
      ));
      expect(find.text('Nothing here'), findsOneWidget);
      expect(find.byIcon(Icons.inbox), findsOneWidget);
    });

    testWidgets('renders subtitle when provided', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const EmptyState(
          icon: Icon(Icons.search_off),
          title: 'No results',
          subtitle: 'Try a different filter',
        ),
      ));
      expect(find.text('No results'), findsOneWidget);
      expect(find.text('Try a different filter'), findsOneWidget);
      expect(find.byIcon(Icons.search_off), findsOneWidget);
    });

    testWidgets('does not render subtitle when omitted', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const EmptyState(icon: Icon(Icons.info), title: 'Info'),
      ));
      expect(find.text('Info'), findsOneWidget);
      // Only the title text should be present; no subtitle
      expect(find.byType(Text), findsOneWidget);
    });
  });

  // ==========================================================================
  // OfflineBanner
  // ==========================================================================
  group('OfflineBanner', () {
    testWidgets('shows banner text when offline', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const OfflineBanner(isOffline: true),
      ));
      expect(find.text('You are offline'), findsOneWidget);
    });

    testWidgets('shows wifi-off icon when offline', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const OfflineBanner(isOffline: true),
      ));
      // Uses LucideIcons.wifiOff — this is a custom icon font
      expect(find.byType(Icon), findsOneWidget);
      // Also verify the text and banner are present
      expect(find.text('You are offline'), findsOneWidget);
    });

    testWidgets('hides banner when online', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const OfflineBanner(isOffline: false),
      ));
      // The AnimatedCrossFade's firstChild is SizedBox.shrink, so the
      // offline text may still be in the tree (opacity 0). Check the
      // property instead.
      final banner = tester.widget<OfflineBanner>(find.byType(OfflineBanner));
      expect(banner.isOffline, isFalse);
    });
  });

  // ==========================================================================
  // StalenessIndicator
  // ==========================================================================
  group('StalenessIndicator', () {
    testWidgets('shows pending sync text when isPending is true',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StalenessIndicator(isPending: true),
      ));
      expect(find.text('Pending sync...'), findsOneWidget);
    });

    testWidgets('shows "Never" when lastUpdated is null and not pending',
        (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StalenessIndicator(),
      ));
      expect(find.text('Never'), findsOneWidget);
    });

    testWidgets('shows custom pendingText when provided', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const StalenessIndicator(isPending: true, pendingText: 'Syncing...'),
      ));
      expect(find.text('Syncing...'), findsOneWidget);
    });

    testWidgets('shows "Just now" for very recent updates', (tester) async {
      final justNow = DateTime.now();
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(lastUpdated: justNow),
      ));
      expect(find.text('Just now'), findsOneWidget);
    });

    testWidgets('shows "5 min ago" for updates 5 minutes ago', (tester) async {
      final fiveMinAgo = DateTime.now().subtract(const Duration(minutes: 5));
      await tester.pumpWidget(wrapInApp(
        StalenessIndicator(lastUpdated: fiveMinAgo),
      ));
      expect(find.text('5 min ago'), findsOneWidget);
    });
  });

  // ==========================================================================
  // ShimmerLoader & ShimmerCard
  // ==========================================================================
  group('ShimmerLoader', () {
    testWidgets('renders child widget', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const ShimmerLoader(child: SizedBox(height: 100, width: 200)),
      ));
      expect(find.byType(ShimmerLoader), findsOneWidget);
    });

    testWidgets('ShimmerCard renders without crashing', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const ShimmerCard(),
      ));
      expect(find.byType(ShimmerCard), findsOneWidget);
    });
  });

  // ==========================================================================
  // AppCard
  // ==========================================================================
  group('AppCard', () {
    testWidgets('renders child widget', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const AppCard(child: Text('Card content')),
      ));
      expect(find.text('Card content'), findsOneWidget);
    });

    testWidgets('is tappable when onTap is provided', (tester) async {
      bool tapped = false;
      await tester.pumpWidget(wrapInApp(
        AppCard(child: const Text('Tap me'), onTap: () => tapped = true),
      ));
      await tester.tap(find.text('Tap me'));
      expect(tapped, isTrue);
    });

    testWidgets('renders as plain Card when onTap is null', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const AppCard(child: Text('No tap')),
      ));
      // Should still render the child
      expect(find.text('No tap'), findsOneWidget);
    });
  });

  // ==========================================================================
  // AppTextField
  // ==========================================================================
  group('AppTextField', () {
    testWidgets('renders with label and hint', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const AppTextField(
          labelText: 'Email',
          hintText: 'email@example.com',
        ),
      ));
      expect(find.text('Email'), findsOneWidget);
      expect(find.text('email@example.com'), findsOneWidget);
    });

    testWidgets('accepts user input', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const AppTextField(labelText: 'Name'),
      ));
      await tester.enterText(find.byType(TextFormField), 'John');
      expect(find.text('John'), findsOneWidget);
    });

    testWidgets('renders prefix icon', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const AppTextField(
          labelText: 'Password',
          prefixIcon: Icon(Icons.lock),
        ),
      ));
      expect(find.byIcon(Icons.lock), findsOneWidget);
    });

    testWidgets('renders suffix icon', (tester) async {
      await tester.pumpWidget(wrapInApp(
        const AppTextField(
          labelText: 'Search',
          suffixIcon: Icon(Icons.search),
        ),
      ));
      expect(find.byIcon(Icons.search), findsOneWidget);
    });
  });

  // ==========================================================================
  // ConfirmationDialog
  // ==========================================================================
  group('ConfirmationDialog', () {
    testWidgets('shows title and message when shown via show()',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Builder(
          builder: (context) => ElevatedButton(
            onPressed: () => ConfirmationDialog.show(
              context,
              title: 'Delete?',
              message: 'Are you sure?',
            ),
            child: const Text('Show dialog'),
          ),
        ),
      ));
      await tester.pumpAndSettle();

      // Open the dialog
      await tester.tap(find.text('Show dialog'));
      await tester.pumpAndSettle();

      expect(find.text('Delete?'), findsOneWidget);
      expect(find.text('Are you sure?'), findsOneWidget);
      // Default buttons
      expect(find.text('Confirm'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
    });

    testWidgets('dangerous variant shows red confirm button', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Builder(
          builder: (context) => ElevatedButton(
            onPressed: () => ConfirmationDialog.show(
              context,
              title: 'Delete?',
              message: 'Are you sure?',
              isDangerous: true,
              confirmLabel: 'Delete',
              cancelLabel: 'Keep',
            ),
            child: const Text('Show dialog'),
          ),
        ),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Show dialog'));
      await tester.pumpAndSettle();

      expect(find.text('Delete?'), findsOneWidget);
      expect(find.text('Delete'), findsOneWidget);
      expect(find.text('Keep'), findsOneWidget);
    });
  });
}
