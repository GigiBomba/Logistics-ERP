import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:operion_mobile/features/dispatcher/alerts/alert_inbox_screen.dart';
import 'package:operion_mobile/features/dispatcher/home/dispatcher_providers.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/shared/widgets/shimmer_loader.dart';
import 'package:operion_mobile/shared/widgets/empty_state.dart';
import 'package:operion_mobile/shared/widgets/app_card.dart';

// ---------------------------------------------------------------------------
// Mock implementations
// ---------------------------------------------------------------------------

class _MockSecureTokenStore extends SecureTokenStore {
  @override
  Future<bool> hasTokens() async => false;
  @override
  Future<String?> getAccessToken() async => null;
  @override
  Future<String?> getRefreshToken() async => null;
  @override
  Future<void> saveTokens(String access, String refresh) async {}
  @override
  Future<void> clearTokens() async {}
}

class _MockBiometricService extends BiometricService {
  @override
  Future<bool> isAvailable() async => false;
  @override
  Future<bool> authenticate({required String reason}) async => false;
}

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

Map<String, dynamic> _makeAlert({
  int id = 1,
  String type = 'delay',
  String severity = 'high',
  String title = 'Test Alert',
  String description = 'Test description',
  bool isRead = false,
  String createdAt = '2026-07-19T10:00:00',
}) {
  return {
    'id': id,
    'type': type,
    'severity': severity,
    'title': title,
    'description': description,
    'is_read': isRead,
    'created_at': createdAt,
  };
}

final List<Map<String, dynamic>> _sampleAlerts = [
  _makeAlert(
    id: 1,
    type: 'delay',
    severity: 'critical',
    title: 'Major Delay',
    description: 'Vehicle stuck in traffic',
    isRead: false,
  ),
  _makeAlert(
    id: 2,
    type: 'maintenance',
    severity: 'medium',
    title: 'Maintenance Due',
    description: 'Oil change required',
    isRead: true,
  ),
  _makeAlert(
    id: 3,
    type: 'document_expiry',
    severity: 'low',
    title: 'Document Expiring',
    description: 'Insurance expires soon',
    isRead: false,
  ),
  _makeAlert(
    id: 4,
    type: 'compliance',
    severity: 'info',
    title: 'Compliance Check',
    description: 'Annual review needed',
    isRead: true,
    createdAt: '2026-07-18T15:00:00',
  ),
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Creates a [ProviderScope] with overridden providers for this test group.
Widget wrapAlertScreen({
  required List<Map<String, dynamic>> alerts,
}) {
  return ProviderScope(
    overrides: [
      secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
      biometricServiceProvider.overrideWithValue(_MockBiometricService()),
      dispatcherAlertsProvider.overrideWith((ref) async => alerts),
      unreadAlertsCountProvider.overrideWith((ref) => 0),
    ],
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const AlertInboxScreen(),
    ),
  );
}

void main() {
  setUpAll(() async {
    await initializeDateFormatting('en', null);
    await initializeDateFormatting('ro', null);
  });

  // ==========================================================================
  // AlertInboxScreen
  // ==========================================================================
  group('AlertInboxScreen', () {
    testWidgets('shows shimmer loading state', (tester) async {
      // Use a provider that never completes to keep showing loading
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
            biometricServiceProvider.overrideWithValue(_MockBiometricService()),
            dispatcherAlertsProvider.overrideWith(
              (ref) => Completer<List<Map<String, dynamic>>>().future,
            ),
            unreadAlertsCountProvider.overrideWith((ref) => 0),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              DefaultMaterialLocalizations.delegate,
              DefaultWidgetsLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const AlertInboxScreen(),
          ),
        ),
      );
      await tester.pump();

      // Shimmer loader should be present
      expect(find.byType(ShimmerLoader), findsWidgets);
    });

    testWidgets('shows error state with retry button', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
            biometricServiceProvider.overrideWithValue(_MockBiometricService()),
            dispatcherAlertsProvider.overrideWith(
              (ref) => Future.error(Exception('Network error')),
            ),
            unreadAlertsCountProvider.overrideWith((ref) => 0),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              DefaultMaterialLocalizations.delegate,
              DefaultWidgetsLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const AlertInboxScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Error icon and retry button should be visible
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
      expect(find.byIcon(Icons.refresh), findsOneWidget);
    });

    testWidgets('shows empty state when no alerts', (tester) async {
      await tester.pumpWidget(wrapAlertScreen(alerts: []));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(EmptyState), findsOneWidget);
      expect(find.byIcon(Icons.notifications_none), findsOneWidget);
    });

    testWidgets('renders alert cards with data', (tester) async {
      await tester.pumpWidget(wrapAlertScreen(alerts: _sampleAlerts));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Should find all alert titles
      expect(find.text('Major Delay'), findsOneWidget);
      expect(find.text('Maintenance Due'), findsOneWidget);
      expect(find.text('Document Expiring'), findsOneWidget);
      expect(find.text('Compliance Check'), findsOneWidget);

      // Card widgets should be present
      expect(find.byType(AppCard), findsWidgets);
    });

    testWidgets('shows unread indicator for unread alerts', (tester) async {
      await tester.pumpWidget(wrapAlertScreen(alerts: _sampleAlerts));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Two alerts have is_read: false, so two unread dot containers
      // The unread dot is a Container with color AppColors.info
      // We look for the unread containers - they have width: 8, height: 8
      // Since these are hard to differentiate, check the first alert has
      // a small blue dot (AppColors.info = Color(0xFF3B82F6))
      final containers = tester.widgetList<Container>(
        find.byWidgetPredicate(
          (w) =>
              w is Container &&
              w.constraints is BoxConstraints &&
              (w.constraints as BoxConstraints).maxWidth == 8.0 &&
              (w.constraints as BoxConstraints).maxHeight == 8.0,
        ),
      );
      // There are 2 unread alerts
      expect(containers.length, 2);
    });

    testWidgets('severity colors render correctly', (tester) async {
      await tester.pumpWidget(wrapAlertScreen(alerts: _sampleAlerts));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Critical/high severity alerts have error color left border
      // The left border is a Container with width: 4
      final severities = find.byWidgetPredicate(
        (w) =>
            w is Container &&
            w.constraints is BoxConstraints &&
            (w.constraints as BoxConstraints).maxWidth == 4.0,
      );
      // Each of the 4 alerts has a severity border
      expect(severities.evaluate().length, 4);
    });

    testWidgets('alert card is tappable', (tester) async {
      await tester.pumpWidget(wrapAlertScreen(alerts: _sampleAlerts));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Verify the alert card has an InkWell (tappable)
      expect(find.byType(InkWell), findsWidgets);
    });

    testWidgets('shows descriptions on alert cards', (tester) async {
      await tester.pumpWidget(wrapAlertScreen(alerts: _sampleAlerts));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Vehicle stuck in traffic'), findsOneWidget);
      expect(find.text('Oil change required'), findsOneWidget);
      expect(find.text('Insurance expires soon'), findsOneWidget);
      expect(find.text('Annual review needed'), findsOneWidget);
    });

    testWidgets('alert type icons render correctly', (tester) async {
      await tester.pumpWidget(wrapAlertScreen(alerts: _sampleAlerts));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // delay -> Icons.access_time
      expect(find.byIcon(Icons.access_time), findsOneWidget);
      // maintenance -> Icons.build_outlined
      expect(find.byIcon(Icons.build_outlined), findsOneWidget);
      // document_expiry -> Icons.description_outlined
      expect(find.byIcon(Icons.description_outlined), findsOneWidget);
      // compliance -> Icons.shield_outlined
      expect(find.byIcon(Icons.shield_outlined), findsOneWidget);
    });
  });
}
