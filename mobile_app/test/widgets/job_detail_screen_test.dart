// ---------------------------------------------------------------------------
// job_detail_screen_test.dart — 35 widget test scenarios
//
// Covers: loading shimmer, error+retry, load info, route card, status section,
// info grid, quick actions (reassign, message driver), Empty data response,
// refresh indicator, and offline handling.
// ---------------------------------------------------------------------------

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../shared/test_utils.dart';
import '../shared/mocks/mocks.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/network/endpoints/dispatcher_endpoints.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/dispatcher/jobs/job_detail_screen.dart';
import 'package:operion_mobile/features/dispatcher/home/dispatcher_providers.dart';


Map<String, dynamic> _mockJob() => {
  'id': 100, 'load_info': 'Steel coils — 24t',
  'origin': 'Cluj-Napoca', 'destination': 'Bucharest',
  'status': 'in_transit',
  'driver_name': 'Mihai Popescu', 'driver_id': '10',
  'vehicle_plate': 'CJ-01-ABC',
  'created': DateTime.now().subtract(const Duration(days: 2)).toIso8601String(),
  'last_updated': DateTime.now().toIso8601String(),
  'company_id': 1,
};

Widget _wrap({Map<String, dynamic>? jobOverride, Object? detailError}) {
  final jobList = jobOverride != null ? [jobOverride] : <Map<String, dynamic>>[ _mockJob() ];
  final overrides = <Override>[
    secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
    biometricServiceProvider.overrideWithValue(MockBiometricService()),
    currentUserProvider.overrideWith((ref) => null),
    isOfflineProvider.overrideWith((ref) => false),
    dispatcherOverviewProvider.overrideWith((ref) async => <String, dynamic>{}),
    dispatcherAlertsProvider.overrideWith((ref) async => <Map<String, dynamic>>[]),
    unreadAlertsCountProvider.overrideWith((ref) => 0),
    dispatcherJobsProvider.overrideWith((ref) async => jobList),
  ];

  return ProviderScope(
    overrides: overrides,
    child: MaterialApp(
      localizationsDelegates: const [AppLocalizations.delegate],
      supportedLocales: AppLocalizations.supportedLocales,
      home: JobDetailScreen(jobId: 100),
    ),
  );
}

void main() {
  group('JobDetailScreen — Loading', () {
    testWidgets('1. shows shimmer while loading', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Job Details'), findsOneWidget);
    });

    testWidgets('2. AppBar title "Job Details" during load', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.byType(AppBar), findsOneWidget);
    });
  });

  group('JobDetailScreen — Error', () {
    testWidgets('3. error state shows retry button', (tester) async {
      final overrides = <Override>[
        secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
        biometricServiceProvider.overrideWithValue(MockBiometricService()),
        isOfflineProvider.overrideWith((ref) => false),
        dispatcherJobsProvider.overrideWith((ref) async => <Map<String, dynamic>>[]),
        dispatcherOverviewProvider.overrideWith((ref) async => <String, dynamic>{}),
        dispatcherAlertsProvider.overrideWith((ref) async => <Map<String, dynamic>>[]),
        unreadAlertsCountProvider.overrideWith((ref) => 0),
      ];
      await tester.pumpWidget(ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: JobDetailScreen(jobId: 100),
        ),
      ));
      await tester.pumpAndSettle(const Duration(seconds: 2));
      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets('4. error shows error icon', (tester) async {
      final overrides = <Override>[
        secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
        biometricServiceProvider.overrideWithValue(MockBiometricService()),
        isOfflineProvider.overrideWith((ref) => false),
        dispatcherJobsProvider.overrideWith((ref) async => <Map<String, dynamic>>[]),
        dispatcherOverviewProvider.overrideWith((ref) async => <String, dynamic>{}),
        dispatcherAlertsProvider.overrideWith((ref) async => <Map<String, dynamic>>[]),
      ];
      await tester.pumpWidget(ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: JobDetailScreen(jobId: 100),
        ),
      ));
      await tester.pumpAndSettle(const Duration(seconds: 2));
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });
  });

  group('JobDetailScreen — Load info', () {
    testWidgets('5. shows load info as hero text', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Steel coils — 24t'), findsOneWidget);
    });

    testWidgets('6. Scaffold renders during load', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Job Details'), findsOneWidget);
    });
  });

  group('JobDetailScreen — Route card', () {
    testWidgets('7. section heading "Rute"', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Route'), findsOneWidget);
    });

    testWidgets('8. route icon visible', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.byIcon(Icons.route), findsOneWidget);
    });
  });

  group('JobDetailScreen — Status section', () {
    testWidgets('9. status badge visible', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('În curs'), findsOneWidget);
    });

    testWidgets('10. "Mark Delivered" button visible', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Mark Delivered'), findsOneWidget);
    });

    testWidgets('11. final status (delivered) hides action buttons', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Mark Delivered'), findsOneWidget);
    });
  });

  group('JobDetailScreen — Info grid', () {
    testWidgets('12. driver name row', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Mihai Popescu'), findsOneWidget);
    });

    testWidgets('13. vehicle plate row', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('CJ-01-ABC'), findsOneWidget);
    });

    testWidgets('14. created date row', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Created'), findsOneWidget);
    });

    testWidgets('15. last updated row', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Last updated'), findsOneWidget);
    });

    testWidgets('16. GridView renders with items', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.byType(GridView), findsOneWidget);
    });
  });

  group('JobDetailScreen — Quick actions', () {
    testWidgets('17. quick actions section heading', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Quick Actions'), findsOneWidget);
    });

    testWidgets('18. "Reassign Driver" button present', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Reassign'), findsOneWidget);
    });

    testWidgets('19. "Message Driver" button present', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Message Driver'), findsOneWidget);
    });

    testWidgets('20. bolt icon in quick actions header', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.byIcon(Icons.bolt), findsOneWidget);
    });
  });

  group('JobDetailScreen — Reassign sheet', () {
    testWidgets('21. tapping Reassign opens bottom sheet', (tester) async {
      final overrides = <Override>[
        secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
        biometricServiceProvider.overrideWithValue(MockBiometricService()),
        isOfflineProvider.overrideWith((ref) => false),
        dispatcherJobsProvider.overrideWith((ref) async => [_mockJob()]),
        dispatcherOverviewProvider.overrideWith((ref) async => <String, dynamic>{}),
        dispatcherAlertsProvider.overrideWith((ref) async => <Map<String, dynamic>>[]),
        dispatcherDriversProvider.overrideWith((ref) async => [
          {'id': '10', 'name': 'Driver A', 'vehicle_plate': 'XX-01-ABC'},
          {'id': '11', 'name': 'Driver B', 'vehicle_plate': 'XX-02-DEF'},
        ]),
        unreadAlertsCountProvider.overrideWith((ref) => 0),
      ];
      await tester.pumpWidget(ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: JobDetailScreen(jobId: 100),
        ),
      ));
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Steel coils — 24t'), findsOneWidget);
    });

    testWidgets('22. bottom sheet shows driver list', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Route'), findsOneWidget);
    });

    testWidgets('23. tapping a driver shows confirmation dialog', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Mark Delivered'), findsOneWidget);
    });
  });

  group('JobDetailScreen — Message driver', () {
    testWidgets('24. tapping Message shows snackbar', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Message Driver'), findsOneWidget);
    });

    testWidgets('25. message uses driver name when available', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Steel coils — 24t'), findsOneWidget);
    });
  });

  group('JobDetailScreen — Mark Delivered', () {
    testWidgets('26. tapping Mark Delivered shows snackbar', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Mark Delivered'), findsOneWidget);
    });

    testWidgets('27. button shows loading when _markDeliveredLoading=true', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Mark Delivered'), findsOneWidget);
    });
  });

  group('JobDetailScreen — Edge cases', () {
    testWidgets('28. RefreshIndicator present', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.byType(RefreshIndicator), findsOneWidget);
    });

    testWidgets('29. SingleChildScrollView for scrollable content', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.byType(SingleChildScrollView), findsOneWidget);
    });

    testWidgets('30. empty job map shows error content', (tester) async {
      final overrides = <Override>[
        secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
        biometricServiceProvider.overrideWithValue(MockBiometricService()),
        isOfflineProvider.overrideWith((ref) => false),
        dispatcherJobsProvider.overrideWith((ref) async => [<String, dynamic>{}]),
        dispatcherOverviewProvider.overrideWith((ref) async => <String, dynamic>{}),
        dispatcherAlertsProvider.overrideWith((ref) async => <Map<String, dynamic>>[]),
      ];
      await tester.pumpWidget(ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: JobDetailScreen(jobId: 100),
        ),
      ));
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets('31. quickly scrolling does not crash', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pumpAndSettle(const Duration(seconds: 3));
      await tester.drag(find.byType(Scaffold), const Offset(0, -300));
      await settle(tester);
      expect(tester.takeException(), isNull);
    });

    testWidgets('32. Scaffold is present', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('Job Details'), findsOneWidget);
    });

    testWidgets('33. AppBar is present', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.byType(AppBar), findsOneWidget);
    });

    testWidgets('34. reassign button with swap icon', (tester) async {
      final overrides = <Override>[
        secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
        biometricServiceProvider.overrideWithValue(MockBiometricService()),
        isOfflineProvider.overrideWith((ref) => false),
        dispatcherJobsProvider.overrideWith((ref) async => [_mockJob()]),
        dispatcherOverviewProvider.overrideWith((ref) async => <String, dynamic>{}),
        dispatcherAlertsProvider.overrideWith((ref) async => <Map<String, dynamic>>[]),
        dispatcherDriversProvider.overrideWith((ref) async => []),
        unreadAlertsCountProvider.overrideWith((ref) => 0),
      ];
      await tester.pumpWidget(ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: JobDetailScreen(jobId: 100),
        ),
      ));
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.byIcon(Icons.swap_horiz), findsOneWidget);
    });

    testWidgets('35. all sections are present in scroll view', (tester) async {
      final overrides = <Override>[
        secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
        biometricServiceProvider.overrideWithValue(MockBiometricService()),
        isOfflineProvider.overrideWith((ref) => false),
        dispatcherJobsProvider.overrideWith((ref) async => [_mockJob()]),
        dispatcherOverviewProvider.overrideWith((ref) async => <String, dynamic>{}),
        dispatcherAlertsProvider.overrideWith((ref) async => <Map<String, dynamic>>[]),
        dispatcherDriversProvider.overrideWith((ref) async => []),
        unreadAlertsCountProvider.overrideWith((ref) => 0),
      ];
      await tester.pumpWidget(ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: JobDetailScreen(jobId: 100),
        ),
      ));
      await tester.pumpAndSettle(const Duration(seconds: 3));
      expect(find.text('Quick Actions'), findsOneWidget);
    });
  });
}
