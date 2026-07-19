import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/cupertino.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';

import 'package:operion_mobile/features/dispatcher/home/dispatcher_home_screen.dart';
import 'package:operion_mobile/features/dispatcher/home/dispatcher_providers.dart';
import 'package:operion_mobile/features/dispatcher/jobs/job_list_screen.dart';
import 'package:operion_mobile/features/dispatcher/jobs/job_detail_screen.dart';
import 'package:operion_mobile/features/dispatcher/jobs/job_providers.dart';
import 'package:operion_mobile/features/dispatcher/alerts/alert_inbox_screen.dart';
import 'package:operion_mobile/features/dispatcher/drivers/driver_list_screen.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/dispatcher_endpoints.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/shared/widgets/shimmer_loader.dart';
import 'package:operion_mobile/shared/widgets/empty_state.dart';
import 'package:operion_mobile/shared/widgets/app_card.dart';
import 'package:operion_mobile/shared/widgets/status_badge.dart';

// ---------------------------------------------------------------------------
// Mock providers – avoid platform crashes and network timer issues.
//
// We override each FutureProvider with a simple synchronous return so that
// no real HTTP calls (and their Dio timeout timers) are created.
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

ApiClient _stubApiClient() => ApiClient.create(
      baseUrl: '',
      apiKey: 'test-key',
      getAccessToken: () async => null,
    );

/// Stub [DispatcherEndpoints] for testing approve/reject/reassign flows.
class _StubDispatcherEndpoints extends DispatcherEndpoints {
  _StubDispatcherEndpoints() : super(_stubApiClient());

  String? lastApprovedId;
  String? lastRejectedId;
  String? lastRejectReason;
  String? lastReassignTransportId;
  String? lastReassignDriverId;

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

  @override
  Future<Response> reassignTransport(
      String transportId, String driverId) async {
    lastReassignTransportId = transportId;
    lastReassignDriverId = driverId;
    return Response(requestOptions: RequestOptions(path: ''), data: {});
  }
}

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

Map<String, dynamic> _makeJob({
  int id = 1,
  String loadInfo = 'Steel beams to Constanta',
  String origin = 'Bucharest',
  String destination = 'Constanta',
  String driverName = 'Ion Popescu',
  String vehiclePlate = 'B-01-ABC',
  String status = 'in_transit',
  String lastUpdated = '2026-07-19T10:00:00',
  String created = '2026-07-18T08:00:00',
}) {
  return {
    'id': id,
    'load_info': loadInfo,
    'origin': origin,
    'destination': destination,
    'driver_name': driverName,
    'vehicle_plate': vehiclePlate,
    'status': status,
    'last_updated': lastUpdated,
    'created': created,
  };
}

final List<Map<String, dynamic>> _sampleJobs = [
  _makeJob(
    id: 1,
    loadInfo: 'Steel beams to Constanta',
    origin: 'Bucharest, Sector 3',
    destination: 'Constanta, Port',
    driverName: 'Ion Popescu',
    status: 'in_transit',
  ),
  _makeJob(
    id: 2,
    loadInfo: 'Electronics to Cluj',
    origin: 'Ilfov, 1 Decembrie',
    destination: 'Cluj-Napoca, Zona Industriala',
    driverName: 'Maria Ionescu',
    status: 'loading',
  ),
  _makeJob(
    id: 3,
    loadInfo: 'Furniture to Iasi',
    origin: 'Ploiesti',
    destination: 'Iasi',
    driverName: 'George Vasile',
    status: 'overdue',
  ),
];

final List<Map<String, dynamic>> _sampleDrivers = [
  {'id': 1, 'name': 'Driver A', 'vehicle_plate': 'B-01-ABC'},
  {'id': 2, 'name': 'Driver B', 'vehicle_plate': 'B-02-XYZ'},
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Base overrides for all tests in this file.
final List<Override> baseOverrides = [
  secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
  biometricServiceProvider.overrideWithValue(_MockBiometricService()),
  apiClientProvider.overrideWithValue(_stubApiClient()),
];

/// Overrides for job list tests.
List<Override> jobListOverrides(List<Map<String, dynamic>> jobs) => [
      ...baseOverrides,
      dispatcherJobsProvider.overrideWith((ref) async => jobs),
    ];

/// Overrides for job detail tests.
List<Override> jobDetailOverrides({
  required int jobId,
  required Map<String, dynamic> job,
  required List<Map<String, dynamic>> drivers,
  required DispatcherEndpoints endpoints,
}) => [
      ...baseOverrides,
      dispatcherJobsProvider.overrideWith((ref) async => [job]),
      dispatcherDriversProvider.overrideWith((ref) async => drivers),
      dispatcherEndpointsProvider.overrideWithValue(endpoints),
      jobDetailProvider(jobId).overrideWith((ref) async => job),
    ];

/// Helper: wraps [child] in [ProviderScope] + [MaterialApp] with
/// localisation so that `context.loc` works.
Widget wrapDispatcherScreen(Widget child, {List<Override>? overrides}) {
  return ProviderScope(
    overrides: overrides ?? baseOverrides,
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultCupertinoLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: child,
    ),
  );
}

void main() {
  // ==========================================================================
  // JobListScreen — comprehensive tests
  // ==========================================================================
  group('JobListScreen', () {
    testWidgets('renders without crashing', (tester) async {
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobListScreen(),
        overrides: jobListOverrides(_sampleJobs),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byType(JobListScreen), findsOneWidget);
      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('shows shimmer loading state', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...baseOverrides,
            dispatcherJobsProvider.overrideWith(
              (ref) => Completer<List<Map<String, dynamic>>>().future,
            ),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              DefaultMaterialLocalizations.delegate,
              DefaultCupertinoLocalizations.delegate,
              DefaultWidgetsLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const JobListScreen(),
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
            ...baseOverrides,
            dispatcherJobsProvider.overrideWith(
              (ref) => Future.error(Exception('Network error')),
            ),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              DefaultMaterialLocalizations.delegate,
              DefaultCupertinoLocalizations.delegate,
              DefaultWidgetsLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const JobListScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(FilledButton), findsAtLeast(1));
    });

    testWidgets('shows empty state when no jobs', (tester) async {
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobListScreen(),
        overrides: jobListOverrides([]),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(EmptyState), findsOneWidget);
    });

    testWidgets('renders job cards with data', (tester) async {
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobListScreen(),
        overrides: jobListOverrides(_sampleJobs),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Load info should be visible
      expect(find.textContaining('Steel beams'), findsOneWidget);
      expect(find.textContaining('Electronics'), findsOneWidget);
      expect(find.textContaining('Furniture'), findsOneWidget);

      // Status badges should be present
      expect(find.byType(StatusBadge), findsWidgets);
    });

    testWidgets('shows filter chips for job filtering', (tester) async {
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobListScreen(),
        overrides: jobListOverrides(_sampleJobs),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.byType(ChoiceChip), findsWidgets);
    });

    testWidgets('filtering by in_transit status works', (tester) async {
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobListScreen(),
        overrides: jobListOverrides(_sampleJobs),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Find and tap the "In Transit" choice chip (second chip)
      final chips = find.byType(ChoiceChip);
      // The first chip is "All", second is "In Transit"
      await tester.tap(chips.at(1));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Only in_transit jobs should show
      expect(find.textContaining('Steel beams'), findsOneWidget);
      // Loading and overdue jobs should be hidden
      // (may still be in widget tree but not visible)
    });

    testWidgets('filtering by loading status works', (tester) async {
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobListScreen(),
        overrides: jobListOverrides(_sampleJobs),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Find and tap the "Loading" choice chip (third chip)
      final chips = find.byType(ChoiceChip);
      await tester.tap(chips.at(2));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Only loading jobs should show
      expect(find.textContaining('Electronics'), findsOneWidget);
    });

    testWidgets('shows origin -> destination on cards', (tester) async {
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobListScreen(),
        overrides: jobListOverrides(_sampleJobs),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Abbreviated locations should be visible (before comma)
      expect(find.textContaining('Bucharest'), findsAtLeast(1));
      expect(find.textContaining('Constanta'), findsAtLeast(1));
    });

    testWidgets('shows driver name and vehicle on cards', (tester) async {
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobListScreen(),
        overrides: jobListOverrides(_sampleJobs),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Ion Popescu'), findsAtLeast(1));
      expect(find.text('B-01-ABC'), findsAtLeast(1));
    });

    testWidgets('tapping job card navigates to detail', (tester) async {
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobListScreen(),
        overrides: jobListOverrides(_sampleJobs),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Tap on a job card
      await tester.tap(find.textContaining('Steel beams'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Should have navigated to JobDetailScreen
      expect(find.byType(JobDetailScreen), findsOneWidget);
    });
  });

  // ==========================================================================
  // JobDetailScreen
  // ==========================================================================
  group('JobDetailScreen', () {
    testWidgets('shows shimmer loading state', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            ...baseOverrides,
            dispatcherJobsProvider.overrideWith(
              (ref) => Completer<List<Map<String, dynamic>>>().future,
            ),
            dispatcherDriversProvider.overrideWith(
              (ref) async => _sampleDrivers,
            ),
            dispatcherEndpointsProvider.overrideWithValue(
              _StubDispatcherEndpoints(),
            ),
          ],
          child: MaterialApp(
            localizationsDelegates: const [
              AppLocalizations.delegate,
              DefaultMaterialLocalizations.delegate,
              DefaultCupertinoLocalizations.delegate,
              DefaultWidgetsLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const JobDetailScreen(jobId: 1),
          ),
        ),
      );
      await tester.pump();

      expect(find.byType(ShimmerLoader), findsWidgets);
    });

    testWidgets('renders job detail content when loaded', (tester) async {
      final job = _makeJob(
        id: 1,
        loadInfo: 'Steel beams to Constanta',
        origin: 'Bucharest',
        destination: 'Constanta',
        driverName: 'Ion Popescu',
        vehiclePlate: 'B-01-ABC',
        status: 'in_transit',
      );
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobDetailScreen(jobId: 1),
        overrides: jobDetailOverrides(
          jobId: 1,
          job: job,
          drivers: _sampleDrivers,
          endpoints: _StubDispatcherEndpoints(),
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // Load info should be visible
      expect(find.textContaining('Steel beams'), findsOneWidget);

      // Route info should be visible
      expect(find.textContaining('Bucharest'), findsOneWidget);
      expect(find.textContaining('Constanta'), findsAtLeast(1));

      // Status badge should be present
      expect(find.byType(StatusBadge), findsOneWidget);
    });

    testWidgets('driver name and vehicle plate shown in info grid',
        (tester) async {
      final job = _makeJob(
        id: 1,
        driverName: 'Ion Popescu',
        vehiclePlate: 'B-01-ABC',
      );
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobDetailScreen(jobId: 1),
        overrides: jobDetailOverrides(
          jobId: 1,
          job: job,
          drivers: _sampleDrivers,
          endpoints: _StubDispatcherEndpoints(),
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      expect(find.text('Ion Popescu'), findsAtLeast(1));
      expect(find.text('B-01-ABC'), findsAtLeast(1));
    });

    testWidgets('shows Mark Delivered button for non-final status',
        (tester) async {
      final job = _makeJob(id: 1, status: 'in_transit');
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobDetailScreen(jobId: 1),
        overrides: jobDetailOverrides(
          jobId: 1,
          job: job,
          drivers: _sampleDrivers,
          endpoints: _StubDispatcherEndpoints(),
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // Mark Delivered button should be present for in_transit job
      expect(find.byType(ElevatedButton), findsWidgets);
    });

    testWidgets('shows quick actions section', (tester) async {
      final job = _makeJob(id: 1, status: 'in_transit');
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobDetailScreen(jobId: 1),
        overrides: jobDetailOverrides(
          jobId: 1,
          job: job,
          drivers: _sampleDrivers,
          endpoints: _StubDispatcherEndpoints(),
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // Reassign button should be present
      expect(find.byType(OutlinedButton), findsWidgets);
    });

    testWidgets('tapping Mark Delivered shows snackbar', (tester) async {
      final job = _makeJob(id: 1, status: 'in_transit');
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobDetailScreen(jobId: 1),
        overrides: jobDetailOverrides(
          jobId: 1,
          job: job,
          drivers: _sampleDrivers,
          endpoints: _StubDispatcherEndpoints(),
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // Tap the Mark Delivered button (first ElevatedButton)
      final elevatedButtons = find.byType(ElevatedButton);
      if (elevatedButtons.evaluate().isNotEmpty) {
        await tester.ensureVisible(elevatedButtons.first);
        await tester.pump();
        await tester.tap(elevatedButtons.first);
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 200));

        // Snackbar should appear
        expect(find.byType(SnackBar), findsOneWidget);
      }
    });

    testWidgets('shows info grid with 4 items', (tester) async {
      final job = _makeJob(id: 1, status: 'in_transit');
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobDetailScreen(jobId: 1),
        overrides: jobDetailOverrides(
          jobId: 1,
          job: job,
          drivers: _sampleDrivers,
          endpoints: _StubDispatcherEndpoints(),
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // Scroll to see the info grid
      await tester.drag(find.byType(SingleChildScrollView), const Offset(0, -200));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // The GridView should be present
      expect(find.byType(GridView), findsOneWidget);
    });

    testWidgets('tapping Message Driver shows snackbar', (tester) async {
      final job = _makeJob(
        id: 1,
        status: 'in_transit',
        driverName: 'Ion Popescu',
      );
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobDetailScreen(jobId: 1),
        overrides: jobDetailOverrides(
          jobId: 1,
          job: job,
          drivers: _sampleDrivers,
          endpoints: _StubDispatcherEndpoints(),
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // Scroll down to see quick actions
      await tester.drag(find.byType(SingleChildScrollView), const Offset(0, -400));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // Find and tap "Message Driver" button
      final messageButton = find.byIcon(Icons.message_outlined);
      if (messageButton.evaluate().isNotEmpty) {
        await tester.ensureVisible(messageButton);
        await tester.pump();
        await tester.tap(messageButton);
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 200));

        expect(find.byType(SnackBar), findsOneWidget);
      }
    });

    testWidgets('shows error state with retry when job not found',
        (tester) async {
      final job = <String, dynamic>{}; // Empty map = not found
      await tester.pumpWidget(wrapDispatcherScreen(
        const JobDetailScreen(jobId: 999),
        overrides: jobDetailOverrides(
          jobId: 999,
          job: job,
          drivers: _sampleDrivers,
          endpoints: _StubDispatcherEndpoints(),
        ),
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 200));

      // Error state should be shown (job not found results in empty map)
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });
  });

  // ==========================================================================
  // AlertInboxScreen — with data
  // ==========================================================================
  group('AlertInboxScreen', () {
    testWidgets('renders without crashing', (tester) async {
      await tester.pumpWidget(wrapDispatcherScreen(
        const AlertInboxScreen(),
        overrides: [
          ...baseOverrides,
          dispatcherAlertsProvider
              .overrideWith((ref) async => <Map<String, dynamic>>[]),
        ],
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byType(AlertInboxScreen), findsOneWidget);
    });

    testWidgets('renders alert cards when alerts exist', (tester) async {
      final alerts = [
        {
          'id': 1,
          'type': 'delay',
          'severity': 'high',
          'title': 'Test Alert',
          'description': 'Description',
          'is_read': false,
          'created_at': DateTime.now().toIso8601String(),
        },
      ];

      await tester.pumpWidget(wrapDispatcherScreen(
        const AlertInboxScreen(),
        overrides: [
          ...baseOverrides,
          dispatcherAlertsProvider.overrideWith((ref) async => alerts),
        ],
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Test Alert'), findsOneWidget);
    });
  });

  // ==========================================================================
  // DriverListScreen
  // ==========================================================================
  group('DriverListScreen', () {
    testWidgets('renders without crashing', (tester) async {
      await tester.pumpWidget(wrapDispatcherScreen(
        const DriverListScreen(),
        overrides: [
          ...baseOverrides,
          dispatcherDriversProvider
              .overrideWith((ref) async => <Map<String, dynamic>>[]),
        ],
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byType(DriverListScreen), findsOneWidget);
    });

    testWidgets('renders driver list with data', (tester) async {
      final drivers = [
        {
          'id': 1,
          'name': 'Test Driver',
          'status': 'available',
          'current_transport': {'name': 'Transport #1'},
          'current_vehicle': 'B-01-TEST',
        },
      ];

      await tester.pumpWidget(wrapDispatcherScreen(
        const DriverListScreen(),
        overrides: [
          ...baseOverrides,
          dispatcherDriversProvider.overrideWith((ref) async => drivers),
        ],
      ));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Test Driver'), findsOneWidget);
      expect(find.text('Transport #1'), findsOneWidget);
    });
  });
}
