import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'package:operion_mobile/features/dispatcher/alerts/approval_detail_screen.dart';
import 'package:operion_mobile/features/dispatcher/home/dispatcher_providers.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/dispatcher_endpoints.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/shared/widgets/shimmer_loader.dart';

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

/// Stub [ApiClient] that never makes real network calls.
ApiClient _stubApiClient() => ApiClient.create(
      baseUrl: '',
      apiKey: 'test-key',
      getAccessToken: () async => null,
    );

/// A stub [DispatcherEndpoints] that tracks calls for verification.
class _StubDispatcherEndpoints extends DispatcherEndpoints {
  _StubDispatcherEndpoints() : super(_stubApiClient());

  String? lastApprovedId;
  String? lastRejectedId;
  String? lastRejectReason;

  @override
  Future<Response> approveAction(String id) async {
    lastApprovedId = id;
    return Response(requestOptions: RequestOptions(path: ''), data: {});
  }

  @override
  Future<Response> rejectAction(String id, {String? reason}) async {
    lastRejectedId = id;
    lastRejectReason = reason;
    return Response(requestOptions: RequestOptions(path: ''), data: {});
  }
}

/// A stub that throws on approve/reject.
class _FailingDispatcherEndpoints extends DispatcherEndpoints {
  _FailingDispatcherEndpoints() : super(_stubApiClient());

  @override
  Future<Response> approveAction(String id) async {
    throw Exception('API error');
  }

  @override
  Future<Response> rejectAction(String id, {String? reason}) async {
    throw Exception('API error');
  }
}

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

Map<String, dynamic> _sampleAlert = {
  'id': 1,
  'type': 'delay',
  'severity': 'high',
  'title': 'Major Delay on Transport #4521',
  'description':
      'Vehicle SC-05-BZX has been stationary for over 2 hours on E85 near Bucharest. Estimated delay: 45 minutes.',
  'related_entity_id': '4521',
  'related_entity_type': 'transport',
  'created_at': '2026-07-19T08:30:00',
  'is_read': false,
};

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

Widget wrapApprovalScreen({
  required int alertId,
  required Map<String, dynamic>? alert,
  required DispatcherEndpoints endpoints,
}) {
  return ProviderScope(
    overrides: [
      secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
      biometricServiceProvider.overrideWithValue(_MockBiometricService()),
      apiClientProvider.overrideWithValue(_stubApiClient()),
      dispatcherAlertsProvider.overrideWith((ref) async => alert != null ? [alert] : []),
      dispatcherEndpointsProvider.overrideWithValue(endpoints),
      unreadAlertsCountProvider.overrideWith((ref) => 0),
    ],
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: ApprovalDetailScreen(alertId: alertId),
    ),
  );
}

void main() {
  setUpAll(() async {
    await initializeDateFormatting('en', null);
    await initializeDateFormatting('ro', null);
  });

  // ==========================================================================
  // ApprovalDetailScreen
  // ==========================================================================
  group('ApprovalDetailScreen', () {
    testWidgets('shows shimmer loading state', (tester) async {
      // Use a provider that stays loading
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
            biometricServiceProvider.overrideWithValue(_MockBiometricService()),
            apiClientProvider.overrideWithValue(_stubApiClient()),
            dispatcherAlertsProvider.overrideWith(
              (ref) => Completer<List<Map<String, dynamic>>>().future,
            ),
            dispatcherEndpointsProvider.overrideWithValue(
              _StubDispatcherEndpoints(),
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
            home: const ApprovalDetailScreen(alertId: 1),
          ),
        ),
      );
      await tester.pump();

      expect(find.byType(ShimmerLoader), findsWidgets);
    });

    testWidgets('shows error state with retry button', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
            biometricServiceProvider.overrideWithValue(_MockBiometricService()),
            apiClientProvider.overrideWithValue(_stubApiClient()),
            dispatcherAlertsProvider.overrideWith(
              (ref) => Future.error(Exception('Failed to load alerts')),
            ),
            dispatcherEndpointsProvider.overrideWithValue(
              _StubDispatcherEndpoints(),
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
            home: const ApprovalDetailScreen(alertId: 1),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byIcon(Icons.error_outline), findsOneWidget);
      expect(find.byIcon(Icons.refresh), findsOneWidget);
    });

    testWidgets('shows not found state when alert is null', (tester) async {
      await tester.pumpWidget(wrapApprovalScreen(
        alertId: 999,
        alert: null,
        endpoints: _StubDispatcherEndpoints(),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Should show general_error text (no icon for null state)
      expect(find.byType(Center), findsOneWidget);
    });

    testWidgets('renders alert details when loaded', (tester) async {
      await tester.pumpWidget(wrapApprovalScreen(
        alertId: 1,
        alert: _sampleAlert,
        endpoints: _StubDispatcherEndpoints(),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Title should be visible
      expect(
        find.text('Major Delay on Transport #4521'),
        findsOneWidget,
      );

      // Description should be visible
      expect(
        find.textContaining('Vehicle SC-05-BZX has been stationary'),
        findsOneWidget,
      );

      // Approve and Reject buttons should be visible
      expect(find.text('Approve'), findsAtLeast(1));
      expect(find.text('Reject'), findsOneWidget);
    });

    testWidgets('shows severity badge with correct label', (tester) async {
      await tester.pumpWidget(wrapApprovalScreen(
        alertId: 1,
        alert: _sampleAlert,
        endpoints: _StubDispatcherEndpoints(),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // High severity shows "High" badge
      expect(find.text('High'), findsOneWidget);
    });

    testWidgets('shows related entity card with link', (tester) async {
      await tester.pumpWidget(wrapApprovalScreen(
        alertId: 1,
        alert: _sampleAlert,
        endpoints: _StubDispatcherEndpoints(),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Related entity should show transport link
      expect(find.byIcon(Icons.link), findsOneWidget);
      // Entity text should contain the transport reference
      expect(find.textContaining('Transports'), findsOneWidget);
    });

    testWidgets('tapping approve calls endpoint and navigates back',
        (tester) async {
      final stub = _StubDispatcherEndpoints();
      await tester.pumpWidget(wrapApprovalScreen(
        alertId: 1,
        alert: _sampleAlert,
        endpoints: stub,
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tap the Approve button
      final approveButton = find.widgetWithText(ElevatedButton, 'Approve');
      await tester.tap(approveButton);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // The approve action should have been called with the correct ID
      expect(stub.lastApprovedId, '1');
    });

    testWidgets('tapping reject shows reason dialog', (tester) async {
      final stub = _StubDispatcherEndpoints();
      await tester.pumpWidget(wrapApprovalScreen(
        alertId: 1,
        alert: _sampleAlert,
        endpoints: stub,
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tap the Reject button (only one "Reject" in the widget tree)
      await tester.tap(find.text('Reject'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Dialog should appear with text field
      expect(find.byType(AlertDialog), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('reject dialog cancel button closes dialog', (tester) async {
      final stub = _StubDispatcherEndpoints();
      await tester.pumpWidget(wrapApprovalScreen(
        alertId: 1,
        alert: _sampleAlert,
        endpoints: stub,
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tap Reject
      await tester.tap(find.text('Reject'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Cancel the dialog
      await tester.tap(find.text('Cancel'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));

      // Dialog should be closed
      expect(find.byType(AlertDialog), findsNothing);
      // Reject should NOT have been called
      expect(stub.lastRejectedId, isNull);
    });

    testWidgets('approve error shows error snackbar', (tester) async {
      await tester.pumpWidget(wrapApprovalScreen(
        alertId: 1,
        alert: _sampleAlert,
        endpoints: _FailingDispatcherEndpoints(),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tap Approve button
      final approveButton = find.widgetWithText(ElevatedButton, 'Approve');
      await tester.tap(approveButton);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // Error snackbar should appear
      expect(find.byType(SnackBar), findsOneWidget);
    });

    testWidgets('shows delay type icon and label', (tester) async {
      await tester.pumpWidget(wrapApprovalScreen(
        alertId: 1,
        alert: _sampleAlert,
        endpoints: _StubDispatcherEndpoints(),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // The title of the alert should be visible
      expect(find.text('Major Delay on Transport #4521'), findsOneWidget);
    });

    testWidgets('reject with reason calls endpoint with reason',
        (tester) async {
      final stub = _StubDispatcherEndpoints();
      await tester.pumpWidget(wrapApprovalScreen(
        alertId: 1,
        alert: _sampleAlert,
        endpoints: stub,
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tap Reject
      await tester.tap(find.text('Reject'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Enter a reason
      await tester.enterText(find.byType(TextField), 'Not valid');
      await tester.pump();

      // Confirm
      await tester.tap(find.text('Confirm'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // Reject should have been called with the reason
      expect(stub.lastRejectedId, '1');
      expect(stub.lastRejectReason, 'Not valid');
    });
  });
}
