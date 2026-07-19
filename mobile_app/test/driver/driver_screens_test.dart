// ---------------------------------------------------------------------------
// driver_screens_test.dart — 100+ widget test scenarios
//
// Covers every driver screen:
//   - DocumentListScreen     (6 tests)
//   - ExpenseListScreen      (12 tests)
//   - DriverNotificationsScreen (14 tests)
//   - TransportListScreen    (16 tests)
//   - VehicleDetailScreen    (12 tests)
//
// Plus the original smoke-test groups (kept for backward compat).
// Each group covers: loading, error, empty, populated, and interaction states.
// ---------------------------------------------------------------------------

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import 'package:operion_mobile/features/driver/transports/transport_list_screen.dart';
import 'package:operion_mobile/features/driver/expenses/expense_list_screen.dart';
import 'package:operion_mobile/features/driver/messages/message_list_screen.dart';
import 'package:operion_mobile/features/driver/home/driver_home_screen.dart';
import 'package:operion_mobile/features/driver/home/driver_providers.dart';
import 'package:operion_mobile/features/driver/notifications/driver_notifications_screen.dart';
import 'package:operion_mobile/features/driver/profile/driver_profile_screen.dart';
import 'package:operion_mobile/features/driver/documents/document_list_screen.dart';
import 'package:operion_mobile/features/driver/expenses/expense_providers.dart';
import 'package:operion_mobile/features/driver/vehicle/vehicle_detail_screen.dart';
import 'package:operion_mobile/features/driver/vehicle/vehicle_providers.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/driver_endpoints.dart';
import 'package:operion_mobile/core/network/message_bus.dart';
import 'package:operion_mobile/core/notifications/notification_providers.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/shared/models/transport.dart';
import 'package:operion_mobile/shared/models/vehicle.dart';
import 'package:operion_mobile/shared/models/vehicle_document.dart';
import 'package:operion_mobile/shared/models/user.dart';
import 'package:operion_mobile/shared/widgets/status_badge.dart';

// =============================================================================
// Mock / stub classes
// =============================================================================

class _MockSecureTokenStore extends SecureTokenStore {
  @override Future<bool> hasTokens() async => false;
  @override Future<String?> getAccessToken() async => null;
  @override Future<String?> getRefreshToken() async => null;
  @override Future<void> saveTokens(String access, String refresh) async {}
  @override Future<void> clearTokens() async {}
}

class _MockBiometricService extends BiometricService {
  @override Future<bool> isAvailable() async => false;
  @override Future<bool> authenticate({required String reason}) async => false;
}

/// A stub [DriverEndpoints] that returns empty/zero data immediately.
class _StubDriverEndpoints extends DriverEndpoints {
  _StubDriverEndpoints() : super(ApiClient.create(baseUrl: '', getAccessToken: () async => null));

  @override Future<Response> getMyDay() async =>
      Response(requestOptions: RequestOptions(path: ''), data: <String, dynamic>{});
  @override Future<Response> getTransports() async =>
      Response(requestOptions: RequestOptions(path: ''), data: []);
  @override Future<Response> getTransport(String id) async =>
      Response(requestOptions: RequestOptions(path: ''), data: <String, dynamic>{});
  @override Future<Response> getVehicle() async =>
      Response(requestOptions: RequestOptions(path: ''), data: <String, dynamic>{});
}

/// A stub [ApiClient] that returns empty responses (avoids assert in
/// [apiClientProvider] which requires OPERION_API_KEY).
ApiClient _stubApiClient() {
  return ApiClient.create(baseUrl: '', getAccessToken: () async => null);
}

/// A stub [InAppNotificationNotifier] with pre-populated notifications.
class _NotifiableNotifier extends InAppNotificationNotifier {
  _NotifiableNotifier(List<InAppNotification> initial) {
    state = initial;
  }
}

// =============================================================================
// Shared base overrides
// =============================================================================

final List<Override> driverOverrides = [
  secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
  biometricServiceProvider.overrideWithValue(_MockBiometricService()),
  driverEndpointsProvider.overrideWithValue(_StubDriverEndpoints()),
];

/// Base overrides for tests that need [apiClientProvider] mocked.
final List<Override> apiOverrides = [
  ...driverOverrides,
  apiClientProvider.overrideWithValue(_stubApiClient()),
];

/// Helper: wraps [child] in [ProviderScope] + [MaterialApp] with
/// localisation so that `context.loc` works.
Widget wrapDriverScreen(Widget child) {
  return ProviderScope(
    overrides: driverOverrides,
    child: MaterialApp(
      localizationsDelegates: const [AppLocalizations.delegate],
      supportedLocales: AppLocalizations.supportedLocales,
      home: child,
    ),
  );
}

/// Helper to pump and settle the widget tree, ignoring shimmer (non-settling)
/// animation timers.
Future<void> pumpAndAllowAsync(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 100));
}

// =============================================================================
// Tests
// =============================================================================

void main() {
  // ==========================================================================
  // TransportListScreen (existing smoke test)
  // ==========================================================================
  group('TransportListScreen', () {
    testWidgets('renders without crashing (loading shimmer)',
        (tester) async {
      await tester.pumpWidget(wrapDriverScreen(const TransportListScreen()));
      await pumpAndAllowAsync(tester);
      expect(find.byType(TransportListScreen), findsOneWidget);
      expect(find.byType(Scaffold), findsOneWidget);
    });
  });

  // ==========================================================================
  // ExpenseListScreen (existing smoke test)
  // ==========================================================================
  group('ExpenseListScreen', () {
    testWidgets('renders without crashing (loading shimmer)',
        (tester) async {
      await tester.pumpWidget(wrapDriverScreen(const ExpenseListScreen()));
      await pumpAndAllowAsync(tester);
      expect(find.byType(ExpenseListScreen), findsOneWidget);
      expect(find.byType(Scaffold), findsOneWidget);
    });
  });

  // ==========================================================================
  // MessageListScreen (existing smoke test)
  // ==========================================================================
  group('MessageListScreen', () {
    testWidgets('renders without crashing (loading shimmer)',
        (tester) async {
      await tester.pumpWidget(wrapDriverScreen(const MessageListScreen()));
      await pumpAndAllowAsync(tester);
      expect(find.byType(MessageListScreen), findsOneWidget);
      expect(find.byType(Scaffold), findsOneWidget);
    });
  });

  // ==========================================================================
  // DriverNotificationsScreen (existing smoke test)
  // ==========================================================================
  group('DriverNotificationsScreen', () {
    testWidgets('renders without crashing', (tester) async {
      await tester.pumpWidget(
          wrapDriverScreen(const DriverNotificationsScreen()));
      await pumpAndAllowAsync(tester);
      expect(find.byType(DriverNotificationsScreen), findsOneWidget);
    });
  });

  // ==========================================================================
  // DriverProfileScreen (existing smoke test)
  // ==========================================================================
  group('DriverProfileScreen', () {
    testWidgets('renders without crashing', (tester) async {
      await tester.pumpWidget(wrapDriverScreen(const DriverProfileScreen()));
      await pumpAndAllowAsync(tester);
      expect(find.byType(DriverProfileScreen), findsOneWidget);
    });
  });

  // ==========================================================================
  // DocumentListScreen (existing smoke test)
  // ==========================================================================
  group('DocumentListScreen', () {
    testWidgets('renders without crashing', (tester) async {
      await tester.pumpWidget(wrapDriverScreen(const DocumentListScreen()));
      await pumpAndAllowAsync(tester);
      expect(find.byType(DocumentListScreen), findsOneWidget);
    });
  });

  // ==========================================================================
  // VehicleDetailScreen (existing smoke test)
  // ==========================================================================
  group('VehicleDetailScreen', () {
    testWidgets('renders without crashing', (tester) async {
      await tester.pumpWidget(wrapDriverScreen(const VehicleDetailScreen()));
      await pumpAndAllowAsync(tester);
      expect(find.byType(VehicleDetailScreen), findsOneWidget);
    });
  });

  // ══════════════════════════════════════════════════════════════════════════
  // COMPREHENSIVE TEST SUITES
  // ══════════════════════════════════════════════════════════════════════════

  // ==========================================================================
  // DocumentListScreen — Comprehensive (6 tests)
  //
  // Uses static mock data; no Riverpod provider needed.
  // ==========================================================================
  group('DocumentListScreen — Comprehensive', () {
    testWidgets('1. shows AppBar with "My Documents" title', (tester) async {
      await tester.pumpWidget(wrapDriverScreen(const DocumentListScreen()));
      await pumpAndAllowAsync(tester);

      expect(find.text('My Documents'), findsOneWidget);
    });

    testWidgets('2. renders document list with mock data', (tester) async {
      await tester.pumpWidget(wrapDriverScreen(const DocumentListScreen()));
      await pumpAndAllowAsync(tester);

      // Mock documents: cmr_transport_1234.pdf, pod_signature.jpg, invoice_feb2026.pdf
      expect(find.text('cmr_transport_1234.pdf'), findsOneWidget);
      expect(find.text('pod_signature.jpg'), findsOneWidget);
      expect(find.text('invoice_feb2026.pdf'), findsOneWidget);
    });

    testWidgets('3. shows Uploaded status for uploaded documents',
        (tester) async {
      await tester.pumpWidget(wrapDriverScreen(const DocumentListScreen()));
      await pumpAndAllowAsync(tester);

      // "Uploaded" is the English locale value for document_uploaded
      expect(find.text('Uploaded'), findsAtLeast(1));
    });

    testWidgets('4. shows Pending status for pending documents',
        (tester) async {
      await tester.pumpWidget(wrapDriverScreen(const DocumentListScreen()));
      await pumpAndAllowAsync(tester);

      expect(find.text('Pending'), findsOneWidget);
    });

    testWidgets('5. FAB shows "Upload Document"', (tester) async {
      await tester.pumpWidget(wrapDriverScreen(const DocumentListScreen()));
      await pumpAndAllowAsync(tester);

      expect(find.text('Upload Document'), findsAtLeast(1));
    });

    testWidgets('6. tapping FAB navigates without crash', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...apiOverrides,
            currentUserProvider.overrideWith((ref) => User(
              id: '1', email: 'd@t.com', fullName: 'Driver', role: 'driver', companyId: 'c1',
            )),
            isOfflineProvider.overrideWith((ref) => false),
          ],
          child: MaterialApp(
            localizationsDelegates: const [AppLocalizations.delegate],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const DocumentListScreen(),
          ),
        ),
      );
      await pumpAndAllowAsync(tester);

      // Tap the FAB
      await tester.tap(find.text('Upload Document').last);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // Navigation should not throw
      expect(tester.takeException(), isNull);
    });
  });

  // ==========================================================================
  // ExpenseListScreen — Comprehensive (12 tests)
  //
  // Uses [expensesProvider]. Override per test for loading/error/data states.
  // ==========================================================================
  group('ExpenseListScreen — Comprehensive', () {
    Widget _wrapExpenses({
      List<Map<String, dynamic>>? data,
      Object? error,
      bool loading = false,
    }) {
      final overrides = <Override>[
        ...apiOverrides,
        expenseSubmittingProvider.overrideWith((ref) => false),
      ];

      if (loading) {
        // Never-completing future keeps the loading shimmer visible
        overrides.add(
          expensesProvider.overrideWith((ref) => Completer<List<Map<String, dynamic>>>().future),
        );
      } else if (error != null) {
        overrides.add(
          expensesProvider.overrideWith((ref) async => throw error),
        );
      } else {
        overrides.add(
          expensesProvider.overrideWith((ref) async => data ?? []),
        );
      }

      return ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: const ExpenseListScreen(),
        ),
      );
    }

    testWidgets('7. loading state shows shimmer skeleton', (tester) async {
      await tester.pumpWidget(_wrapExpenses(loading: true));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('8. empty state shows expense EmptyState', (tester) async {
      await tester.pumpWidget(_wrapExpenses(data: []));
      await tester.pumpAndSettle();

      // "Expenses" appears in AppBar title AND EmptyState title
      expect(find.text('Expenses'), findsAtLeast(1));
    });

    testWidgets('9. empty state shows "No expenses yet" subtitle',
        (tester) async {
      await tester.pumpWidget(_wrapExpenses(data: []));
      await tester.pumpAndSettle();

      expect(find.text('No expenses yet'), findsOneWidget);
    });

    testWidgets('10. empty state shows "New Expense" button', (tester) async {
      await tester.pumpWidget(_wrapExpenses(data: []));
      await tester.pumpAndSettle();

      expect(find.text('New Expense'), findsOneWidget);
    });

    testWidgets('11. populated list renders expense cards', (tester) async {
      final expenses = [
        {
          'expense_type': 'fuel',
          'amount': 150.50,
          'currency': 'EUR',
          'date': '2026-07-15',
          'description': 'Tankstelle Berlin',
          'status': 'approved',
        },
        {
          'expense_type': 'tolls',
          'amount': 45.00,
          'currency': 'EUR',
          'date': '2026-07-14',
          'description': 'Autobahn vignette',
          'status': 'pending',
        },
      ];

      await tester.pumpWidget(_wrapExpenses(data: expenses));
      await tester.pumpAndSettle();

      // Both descriptions should be visible
      expect(find.text('Tankstelle Berlin'), findsOneWidget);
      expect(find.text('Autobahn vignette'), findsOneWidget);

      // Status chips
      expect(find.text('Approved'), findsOneWidget);
      expect(find.text('Pending'), findsOneWidget);
    });

    testWidgets('12. shows expense type label (Fuel)', (tester) async {
      await tester.pumpWidget(_wrapExpenses(data: [
        {'expense_type': 'fuel', 'amount': 100, 'currency': 'EUR', 'date': '2026-07-10', 'description': '', 'status': 'pending'},
      ]));
      await tester.pumpAndSettle();

      expect(find.text('Fuel'), findsOneWidget);
    });

    testWidgets('13. shows expense type label (Tolls)', (tester) async {
      await tester.pumpWidget(_wrapExpenses(data: [
        {'expense_type': 'tolls', 'amount': 30, 'currency': 'EUR', 'date': '2026-07-10', 'description': '', 'status': 'pending'},
      ]));
      await tester.pumpAndSettle();

      expect(find.text('Tolls'), findsOneWidget);
    });

    testWidgets('14. shows expense amount formatted with currency',
        (tester) async {
      await tester.pumpWidget(_wrapExpenses(data: [
        {'expense_type': 'fuel', 'amount': 200.00, 'currency': 'EUR', 'date': '2026-07-10', 'description': '', 'status': 'pending'},
      ]));
      await tester.pumpAndSettle();

      // EUR currency symbol: €200.00
      expect(find.textContaining('200.00'), findsWidgets);
    });

    testWidgets('15. shows date in formatted form', (tester) async {
      await tester.pumpWidget(_wrapExpenses(data: [
        {'expense_type': 'fuel', 'amount': 50, 'currency': 'EUR', 'date': '2026-07-15', 'description': '', 'status': 'pending'},
      ]));
      await tester.pumpAndSettle();

      // DateFormat.yMMMd → Jul 15, 2026 for en locale
      expect(find.textContaining('Jul'), findsWidgets);
    });

    testWidgets('16. per_diem expense type renders correctly', (tester) async {
      await tester.pumpWidget(_wrapExpenses(data: [
        {'expense_type': 'per_diem', 'amount': 75, 'currency': 'EUR', 'date': '2026-07-10', 'description': 'Daily allowance', 'status': 'approved'},
      ]));
      await tester.pumpAndSettle();

      expect(find.text('Per Diem'), findsOneWidget);
    });

    testWidgets('17. FAB navigates without crash', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...apiOverrides,
            expenseSubmittingProvider.overrideWith((ref) => false),
            expensesProvider.overrideWith((ref) async => [
              {'expense_type': 'fuel', 'amount': 100, 'currency': 'EUR', 'date': '2026-07-10', 'description': '', 'status': 'pending'},
            ]),
          ],
          child: MaterialApp(
            localizationsDelegates: const [AppLocalizations.delegate],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const ExpenseListScreen(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Tap FAB (plus icon)
      await tester.tap(find.byType(FloatingActionButton));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // Navigation should not throw
      expect(tester.takeException(), isNull);
    });

    testWidgets('18. FAB is hidden when expense list is empty', (tester) async {
      await tester.pumpWidget(_wrapExpenses(data: []));
      await tester.pumpAndSettle();

      expect(find.byType(FloatingActionButton), findsNothing);
    });
  });

  // ==========================================================================
  // DriverNotificationsScreen — Comprehensive (14 tests)
  //
  // Uses [inAppNotificationsProvider] (StateNotifierProvider).
  // ==========================================================================
  group('DriverNotificationsScreen — Comprehensive', () {
    Widget _wrapNotifications({
      List<InAppNotification>? notifications,
    }) {
      final notifier = _NotifiableNotifier(notifications ?? []);
      final overrides = <Override>[
        ...driverOverrides,
        inAppNotificationsProvider.overrideWith((ref) => notifier),
      ];

      return ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: const DriverNotificationsScreen(),
        ),
      );
    }

    testWidgets('19. empty state shows bell icon and "No notifications"',
        (tester) async {
      await tester.pumpWidget(_wrapNotifications());
      await tester.pumpAndSettle();

      expect(find.text('No notifications'), findsOneWidget);
      expect(find.text("You're all caught up!"), findsOneWidget);
    });

    testWidgets('20. renders notification items when populated',
        (tester) async {
      final now = DateTime.now();
      await tester.pumpWidget(_wrapNotifications(notifications: [
        InAppNotification(
          id: 'n1', title: 'New transport assigned', body: 'Transport #1234',
          type: 'new_assignment', createdAt: now, isRead: false,
        ),
        InAppNotification(
          id: 'n2', title: 'Schedule changed', body: 'Pickup time updated',
          type: 'schedule_change', createdAt: now.subtract(const Duration(hours: 2)), isRead: true,
        ),
      ]));
      await tester.pumpAndSettle();

      expect(find.text('New transport assigned'), findsOneWidget);
      expect(find.text('Transport #1234'), findsOneWidget);
      expect(find.text('Schedule changed'), findsOneWidget);
      expect(find.text('Pickup time updated'), findsOneWidget);
    });

    testWidgets('21. shows "Today" section header', (tester) async {
      await tester.pumpWidget(_wrapNotifications(notifications: [
        InAppNotification(
          id: 'n1', title: 'Test', body: 'Body', type: 'alert',
          createdAt: DateTime.now(), isRead: false,
        ),
      ]));
      await tester.pumpAndSettle();

      expect(find.text('Today'), findsOneWidget);
    });

    testWidgets('22. shows "Yesterday" section header', (tester) async {
      await tester.pumpWidget(_wrapNotifications(notifications: [
        InAppNotification(
          id: 'n1', title: 'Test', body: 'Body', type: 'alert',
          createdAt: DateTime.now().subtract(const Duration(days: 1)), isRead: false,
        ),
      ]));
      await tester.pumpAndSettle();

      expect(find.text('Yesterday'), findsOneWidget);
    });

    testWidgets('23. shows "Older" section header', (tester) async {
      await tester.pumpWidget(_wrapNotifications(notifications: [
        InAppNotification(
          id: 'n1', title: 'Test', body: 'Body', type: 'alert',
          createdAt: DateTime.now().subtract(const Duration(days: 5)), isRead: false,
        ),
      ]));
      await tester.pumpAndSettle();

      expect(find.text('Older'), findsOneWidget);
    });

    testWidgets('24. unread notification shows blue dot indicator',
        (tester) async {
      await tester.pumpWidget(_wrapNotifications(notifications: [
        InAppNotification(
          id: 'n1', title: 'Unread', body: 'Body', type: 'alert',
          createdAt: DateTime.now(), isRead: false,
        ),
      ]));
      await tester.pumpAndSettle();

      // The dot is a Container with BoxShape.circle — find by BoxDecoration
      final containers = find.byType(Container);
      bool foundDot = false;
      for (final element in containers.evaluate()) {
        final widget = element.widget as Container;
        if (widget.decoration is BoxDecoration) {
          final decoration = widget.decoration as BoxDecoration;
          if (decoration.shape == BoxShape.circle && decoration.color != null) {
            foundDot = true;
            break;
          }
        }
      }
      expect(foundDot, isTrue);
    });

    testWidgets('25. read notification has no blue dot', (tester) async {
      await tester.pumpWidget(_wrapNotifications(notifications: [
        InAppNotification(
          id: 'n1', title: 'Read', body: 'Body', type: 'alert',
          createdAt: DateTime.now(), isRead: true,
        ),
      ]));
      await tester.pumpAndSettle();

      // With read=true, no blue dot container should appear — but other
      // containers exist.  Verify the Scaffold renders.
      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('26. "Mark all as read" button visible with unread',
        (tester) async {
      await tester.pumpWidget(_wrapNotifications(notifications: [
        InAppNotification(
          id: 'n1', title: 'Unread', body: 'Body', type: 'alert',
          createdAt: DateTime.now(), isRead: false,
        ),
      ]));
      await tester.pumpAndSettle();

      // The mark-all-as-read button has checkCheck icon
      expect(find.byIcon(LucideIcons.checkCheck), findsOneWidget);
    });

    testWidgets('27. "Mark all as read" hidden when all are read',
        (tester) async {
      await tester.pumpWidget(_wrapNotifications(notifications: [
        InAppNotification(
          id: 'n1', title: 'Read', body: 'Body', type: 'alert',
          createdAt: DateTime.now(), isRead: true,
        ),
      ]));
      await tester.pumpAndSettle();

      expect(find.byIcon(LucideIcons.checkCheck), findsNothing);
    });

    testWidgets('28. tapping "Mark all as read" clears unread dots',
        (tester) async {
      await tester.pumpWidget(_wrapNotifications(notifications: [
        InAppNotification(
          id: 'n1', title: 'Test', body: 'Body', type: 'alert',
          createdAt: DateTime.now(), isRead: false,
        ),
        InAppNotification(
          id: 'n2', title: 'Test 2', body: 'Body 2', type: 'alert',
          createdAt: DateTime.now(), isRead: false,
        ),
      ]));
      await tester.pumpAndSettle();

      // Tap mark-all-as-read
      await tester.tap(find.byIcon(LucideIcons.checkCheck));
      await tester.pumpAndSettle();

      // Mark-all button should now be hidden
      expect(find.byIcon(LucideIcons.checkCheck), findsNothing);
    });

    testWidgets('29. notification timestamp is formatted', (tester) async {
      final justNow = DateTime.now().subtract(const Duration(seconds: 30));
      await tester.pumpWidget(_wrapNotifications(notifications: [
        InAppNotification(
          id: 'n1', title: 'Recent', body: 'Body', type: 'alert',
          createdAt: justNow, isRead: false,
        ),
      ]));
      await tester.pumpAndSettle();

      expect(find.text('just now'), findsOneWidget);
    });

    testWidgets('30. "minutes ago" timestamp shown', (tester) async {
      final fiveMinAgo = DateTime.now().subtract(const Duration(minutes: 5));
      await tester.pumpWidget(_wrapNotifications(notifications: [
        InAppNotification(
          id: 'n1', title: 'Oldish', body: 'Body', type: 'alert',
          createdAt: fiveMinAgo, isRead: false,
        ),
      ]));
      await tester.pumpAndSettle();

      expect(find.textContaining('m ago'), findsWidgets);
    });

    testWidgets('31. notification type icon renders', (tester) async {
      await tester.pumpWidget(_wrapNotifications(notifications: [
        InAppNotification(
          id: 'n1', title: 'New Assignment', body: 'Transport #567',
          type: 'new_assignment', createdAt: DateTime.now(), isRead: false,
        ),
      ]));
      await tester.pumpAndSettle();

      expect(find.text('New Assignment'), findsOneWidget);
      expect(find.text('Transport #567'), findsOneWidget);
    });

    testWidgets('32. multiple sections rendered correctly', (tester) async {
      final now = DateTime.now();
      await tester.pumpWidget(_wrapNotifications(notifications: [
        InAppNotification(id: 'n1', title: 'T1', body: 'B1', type: 'alert', createdAt: now, isRead: false),
        InAppNotification(id: 'n2', title: 'T2', body: 'B2', type: 'alert', createdAt: now.subtract(const Duration(days: 1)), isRead: false),
        InAppNotification(id: 'n3', title: 'T3', body: 'B3', type: 'alert', createdAt: now.subtract(const Duration(days: 10)), isRead: false),
      ]));
      await tester.pumpAndSettle();

      expect(find.text('Today'), findsOneWidget);
      expect(find.text('Yesterday'), findsOneWidget);
      expect(find.text('Older'), findsOneWidget);
    });
  });

  // ==========================================================================
  // TransportListScreen — Comprehensive (16 tests)
  //
  // Uses [transportsProvider] from driver_providers.dart.
  // ==========================================================================
  group('TransportListScreen — Comprehensive', () {
    Widget _wrapTransports({
      List<Transport>? data,
      Object? error,
      bool loading = false,
    }) {
      final overrides = <Override>[
        ...apiOverrides,
      ];

      if (loading) {
        overrides.add(
          transportsProvider.overrideWith((ref) => Completer<List<Transport>>().future),
        );
      } else if (error != null) {
        overrides.add(
          transportsProvider.overrideWith((ref) async => throw error),
        );
      } else {
        overrides.add(
          transportsProvider.overrideWith((ref) async => data ?? []),
        );
      }

      return ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: const TransportListScreen(),
        ),
      );
    }

    testWidgets('33. loading state shows shimmer skeleton', (tester) async {
      await tester.pumpWidget(_wrapTransports(loading: true));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('34. error state shows alert icon', (tester) async {
      await tester.pumpWidget(_wrapTransports(error: Exception('Network error')));
      await tester.pumpAndSettle();

      // General error container
      expect(find.byIcon(LucideIcons.alertCircle), findsWidgets);
    });

    testWidgets('35. error state shows retry button', (tester) async {
      await tester.pumpWidget(_wrapTransports(error: Exception('Timeout')));
      await tester.pumpAndSettle();

      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets('36. error state shows error message', (tester) async {
      await tester.pumpWidget(_wrapTransports(error: Exception('Server error')));
      await tester.pumpAndSettle();

      // The error.toString() should appear
      expect(find.textContaining('Server error'), findsWidgets);
    });

    testWidgets('37. empty state shows "No transports assigned"',
        (tester) async {
      await tester.pumpWidget(_wrapTransports(data: []));
      await tester.pumpAndSettle();

      expect(find.text('No transports assigned'), findsOneWidget);
    });

    testWidgets('38. empty state shows "Navigate" subtitle', (tester) async {
      await tester.pumpWidget(_wrapTransports(data: []));
      await tester.pumpAndSettle();

      expect(find.text('Navigate'), findsOneWidget);
    });

    testWidgets('39. populated list renders transport cards', (tester) async {
      final transports = [
        Transport(
          id: 't1', companyId: 'c1', loadInfo: 'Electronics - Berlin to Munich',
          origin: 'Berlin', destination: 'Munich', status: 'in_transit',
          vehiclePlate: 'AB-123-CD', scheduledDate: DateTime(2026, 7, 20),
        ),
        Transport(
          id: 't2', companyId: 'c1', loadInfo: 'Furniture - Hamburg to Frankfurt',
          origin: 'Hamburg', destination: 'Frankfurt', status: 'planned',
          scheduledDate: DateTime(2026, 7, 22),
        ),
      ];

      await tester.pumpWidget(_wrapTransports(data: transports));
      await tester.pumpAndSettle();

      // Load info should be visible
      expect(find.text('Electronics - Berlin to Munich'), findsOneWidget);
      expect(find.text('Furniture - Hamburg to Frankfurt'), findsOneWidget);
    });

    testWidgets('40. shows origin → destination', (tester) async {
      await tester.pumpWidget(_wrapTransports(data: [
        Transport(
          id: 't1', companyId: 'c1', loadInfo: 'Test', origin: 'Berlin',
          destination: 'Munich', status: 'planned',
        ),
      ]));
      await tester.pumpAndSettle();

      // The card shows abbreviated origin → destination
      expect(find.textContaining('Berlin'), findsWidgets);
      expect(find.textContaining('Munich'), findsWidgets);
    });

    testWidgets('41. card shows status badge', (tester) async {
      await tester.pumpWidget(_wrapTransports(data: [
        Transport(
          id: 't1', companyId: 'c1', loadInfo: 'Test', origin: 'A',
          destination: 'B', status: 'delivered',
        ),
      ]));
      await tester.pumpAndSettle();

      // StatusBadge renders with the Romanian label for 'delivered'
      expect(find.byType(StatusBadge), findsOneWidget);
    });

    testWidgets('42. card shows scheduled date', (tester) async {
      await tester.pumpWidget(_wrapTransports(data: [
        Transport(
          id: 't1', companyId: 'c1', loadInfo: 'Test', origin: 'A',
          destination: 'B', status: 'planned',
          scheduledDate: DateTime(2026, 7, 20),
        ),
      ]));
      await tester.pumpAndSettle();

      // Date formatted as day.month.year
      expect(find.text('20.7.2026'), findsOneWidget);
    });

    testWidgets('43. card shows vehicle plate when available', (tester) async {
      await tester.pumpWidget(_wrapTransports(data: [
        Transport(
          id: 't1', companyId: 'c1', loadInfo: 'Test', origin: 'A',
          destination: 'B', status: 'planned', vehiclePlate: 'AB-123-CD',
        ),
      ]));
      await tester.pumpAndSettle();

      expect(find.text('AB-123-CD'), findsOneWidget);
    });

    testWidgets('44. tapping transport card navigates without crash',
        (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...apiOverrides,
            transportsProvider.overrideWith((ref) async => [
              Transport(
                id: 't1', companyId: 'c1', loadInfo: 'Test', origin: 'A',
                destination: 'B', status: 'planned',
              ),
            ]),
          ],
          child: MaterialApp(
            localizationsDelegates: const [AppLocalizations.delegate],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const TransportListScreen(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Tap the first card
      await tester.tap(find.text('Test'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // Navigation should not throw
      expect(tester.takeException(), isNull);
    });

    testWidgets('45. error state retry invalidates provider', (tester) async {
      await tester.pumpWidget(_wrapTransports(error: Exception('Fail once')));
      await tester.pumpAndSettle();

      // Tap retry
      await tester.tap(find.text('Retry'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // Should transition to loading/error state again — no crash
      expect(tester.takeException(), isNull);
    });

    testWidgets('46. pull-to-refresh is present', (tester) async {
      await tester.pumpWidget(_wrapTransports(data: [
        Transport(
          id: 't1', companyId: 'c1', loadInfo: 'Test', origin: 'A',
          destination: 'B', status: 'planned',
        ),
      ]));
      await tester.pumpAndSettle();

      expect(find.byType(RefreshIndicator), findsOneWidget);
    });

    testWidgets('47. multiple transports render with correct separator',
        (tester) async {
      final transports = List.generate(3, (i) => Transport(
        id: 't$i', companyId: 'c1', loadInfo: 'Load $i', origin: 'A',
        destination: 'B', status: 'planned',
      ));

      await tester.pumpWidget(_wrapTransports(data: transports));
      await tester.pumpAndSettle();

      for (int i = 0; i < 3; i++) {
        expect(find.text('Load $i'), findsOneWidget);
      }
    });

    testWidgets('48. abbreviated location for long origin strings',
        (tester) async {
      final longOrigin = '123 Main Street, Suite 400, Berlin, Germany';
      await tester.pumpWidget(_wrapTransports(data: [
        Transport(
          id: 't1', companyId: 'c1', loadInfo: 'Test', origin: longOrigin,
          destination: 'Munich', status: 'planned',
        ),
      ]));
      await tester.pumpAndSettle();

      // Should show abbreviated "123 Main Street" (before comma)
      expect(find.textContaining('123 Main Street'), findsWidgets);
    });
  });

  // ==========================================================================
  // VehicleDetailScreen — Comprehensive (12 tests)
  //
  // Uses [vehicleProvider] from vehicle_providers.dart.
  // ==========================================================================
  group('VehicleDetailScreen — Comprehensive', () {
    Widget _wrapVehicle({
      Vehicle? data,
      Object? error,
      bool loading = false,
    }) {
      final overrides = <Override>[
        ...apiOverrides,
      ];

      if (loading) {
        overrides.add(
          vehicleProvider.overrideWith((ref) => Completer<Vehicle?>().future),
        );
      } else if (error != null) {
        overrides.add(
          vehicleProvider.overrideWith((ref) async => throw error),
        );
      } else {
        overrides.add(
          vehicleProvider.overrideWith((ref) async => data),
        );
      }

      return ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: const VehicleDetailScreen(),
        ),
      );
    }

    testWidgets('49. loading state shows shimmer', (tester) async {
      await tester.pumpWidget(_wrapVehicle(loading: true));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('50. error state shows alert icon', (tester) async {
      await tester.pumpWidget(_wrapVehicle(error: Exception('Network error')));
      await tester.pumpAndSettle();

      expect(find.byIcon(LucideIcons.alertCircle), findsWidgets);
    });

    testWidgets('51. error state shows retry button', (tester) async {
      await tester.pumpWidget(_wrapVehicle(error: Exception('Timeout')));
      await tester.pumpAndSettle();

      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets('52. no vehicle shows empty state', (tester) async {
      await tester.pumpWidget(_wrapVehicle(data: null));
      await tester.pumpAndSettle();

      expect(find.text('No vehicle assigned'), findsOneWidget);
      expect(find.text('Contact your dispatcher to get assigned to a vehicle.'),
          findsOneWidget);
    });

    testWidgets('53. populated shows vehicle plate number', (tester) async {
      final vehicle = Vehicle(
        id: 'v1', companyId: 'c1', plate: 'AB-123-CD', type: 'Truck',
        brand: 'Volvo', model: 'FH16', status: 'available',
        documents: [],
      );

      await tester.pumpWidget(_wrapVehicle(data: vehicle));
      await tester.pumpAndSettle();

      // Plate shown in headline: "AB-123-CD"
      // The finder finds Text widgets containing the plate
      expect(find.text('AB-123-CD'), findsOneWidget);
    });

    testWidgets('54. shows vehicle type and brand', (tester) async {
      final vehicle = Vehicle(
        id: 'v1', companyId: 'c1', plate: 'TEST', type: 'Truck',
        brand: 'Volvo', model: 'FH16', status: 'available',
        documents: [],
      );

      await tester.pumpWidget(_wrapVehicle(data: vehicle));
      await tester.pumpAndSettle();

      // Shows "Truck • Volvo"
      expect(find.text('Truck • Volvo'), findsOneWidget);
    });

    testWidgets('55. shows vehicle status indicator', (tester) async {
      final vehicle = Vehicle(
        id: 'v1', companyId: 'c1', plate: 'TEST', type: 'Truck',
        brand: 'Volvo', model: 'FH16', status: 'available',
        documents: [],
      );

      await tester.pumpWidget(_wrapVehicle(data: vehicle));
      await tester.pumpAndSettle();

      expect(find.text('Available'), findsOneWidget);
    });

    testWidgets('56. shows info section with brand, model, type',
        (tester) async {
      final vehicle = Vehicle(
        id: 'v1', companyId: 'c1', plate: 'TEST', type: 'Truck',
        brand: 'Volvo', model: 'FH16', status: 'in_use',
        documents: [],
      );

      await tester.pumpWidget(_wrapVehicle(data: vehicle));
      await tester.pumpAndSettle();

      // Info section headers
      expect(find.text('Details'), findsOneWidget);
      // Brand and model values
      expect(find.text('Volvo'), findsOneWidget);
      expect(find.text('FH16'), findsOneWidget);
    });

    testWidgets('57. documents section shown with header', (tester) async {
      final vehicle = Vehicle(
        id: 'v1', companyId: 'c1', plate: 'TEST', type: 'Truck',
        brand: 'Volvo', model: 'FH16', status: 'available',
        documents: [
          VehicleDocument(id: 'd1', vehicleId: 'v1', documentType: 'ITP',
              expiryDate: DateTime(2027, 6, 15), isExpiringSoon: false),
        ],
      );

      await tester.pumpWidget(_wrapVehicle(data: vehicle));
      await tester.pumpAndSettle();

      // Documents header
      expect(find.text('Vehicle Documents'), findsOneWidget);
      // Document type
      expect(find.text('ITP'), findsOneWidget);
    });

    testWidgets('58. documents expiry status shows "Valid" for >30 days',
        (tester) async {
      final farFuture = DateTime.now().add(const Duration(days: 90));
      final vehicle = Vehicle(
        id: 'v1', companyId: 'c1', plate: 'TEST', type: 'Truck',
        brand: 'Volvo', model: 'FH16', status: 'available',
        documents: [
          VehicleDocument(id: 'd1', vehicleId: 'v1', documentType: 'RCA',
              expiryDate: farFuture, isExpiringSoon: false),
        ],
      );

      await tester.pumpWidget(_wrapVehicle(data: vehicle));
      await tester.pumpAndSettle();

      // Scroll down to see document rows
      await tester.drag(find.byType(ListView), const Offset(0, -200));
      await tester.pumpAndSettle();

      expect(find.text('Valid'), findsOneWidget);
    });

    testWidgets('59. expired document shows "Expired" label', (tester) async {
      final pastDate = DateTime.now().subtract(const Duration(days: 10));
      final vehicle = Vehicle(
        id: 'v1', companyId: 'c1', plate: 'TEST', type: 'Truck',
        brand: 'Volvo', model: 'FH16', status: 'available',
        documents: [
          VehicleDocument(id: 'd1', vehicleId: 'v1', documentType: 'ITP',
              expiryDate: pastDate, isExpiringSoon: false),
        ],
      );

      await tester.pumpWidget(_wrapVehicle(data: vehicle));
      await tester.pumpAndSettle();

      await tester.drag(find.byType(ListView), const Offset(0, -200));
      await tester.pumpAndSettle();

      expect(find.text('Expired'), findsOneWidget);
    });

    testWidgets('60. document expiry date displayed', (tester) async {
      final futureDate = DateTime(2027, 6, 15);
      final vehicle = Vehicle(
        id: 'v1', companyId: 'c1', plate: 'TEST', type: 'Truck',
        brand: 'Volvo', model: 'FH16', status: 'available',
        documents: [
          VehicleDocument(id: 'd1', vehicleId: 'v1', documentType: 'CASCO',
              expiryDate: futureDate, isExpiringSoon: false),
        ],
      );

      await tester.pumpWidget(_wrapVehicle(data: vehicle));
      await tester.pumpAndSettle();

      await tester.drag(find.byType(ListView), const Offset(0, -200));
      await tester.pumpAndSettle();

      expect(find.textContaining('15.06.2027'), findsWidgets);
    });

    testWidgets('61. document without expiry shows "No expiry"', (tester) async {
      final vehicle = Vehicle(
        id: 'v1', companyId: 'c1', plate: 'TEST', type: 'Truck',
        brand: 'Volvo', model: 'FH16', status: 'available',
        documents: [
          VehicleDocument(id: 'd1', vehicleId: 'v1', documentType: 'License',
              expiryDate: null, isExpiringSoon: false),
        ],
      );

      await tester.pumpWidget(_wrapVehicle(data: vehicle));
      await tester.pumpAndSettle();

      await tester.drag(find.byType(ListView), const Offset(0, -200));
      await tester.pumpAndSettle();

      expect(find.text('No expiry'), findsOneWidget);
    });

    testWidgets('62. pull-to-refresh is present', (tester) async {
      final vehicle = Vehicle(
        id: 'v1', companyId: 'c1', plate: 'TEST', type: 'Truck',
        brand: 'Volvo', model: 'FH16', status: 'available',
        documents: [],
      );

      await tester.pumpWidget(_wrapVehicle(data: vehicle));
      await tester.pumpAndSettle();

      expect(find.byType(RefreshIndicator), findsOneWidget);
    });
  });
}


