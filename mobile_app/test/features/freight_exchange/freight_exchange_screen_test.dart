import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/freight_exchange_endpoints.dart';
import 'package:operion_mobile/features/freight_exchange/models/freight_load.dart';
import 'package:operion_mobile/features/freight_exchange/providers/freight_exchange_providers.dart';
import 'package:operion_mobile/features/freight_exchange/screens/freight_exchange_screen.dart';

// ── Fake dependencies ─────────────────────────────────────────────────────

class _FakeEndpoints extends FreightExchangeEndpoints {
  _FakeEndpoints()
      : super(ApiClient.create(
          baseUrl: 'https://test.com',
          getAccessToken: () async => null,
        ));
}

class _FakeNotifier extends FreightExchangeNotifier {
  _FakeNotifier() : super(_FakeEndpoints());

  FreightExchangeState _manualState = const FreightExchangeInitial();
  bool loadLoadsCalled = false;
  bool importLoadCalled = false;
  bool evaluateLoadCalled = false;
  String? lastOrigin;
  String? lastDestination;
  String? lastDate;
  String? lastCargoType;

  @override
  FreightExchangeState get state => _manualState;

  set manualState(FreightExchangeState value) => _manualState = value;

  @override
  Future<void> loadLoads({
    String? origin,
    String? destination,
    String? date,
    String? cargoType,
  }) async {
    loadLoadsCalled = true;
    lastOrigin = origin;
    lastDestination = destination;
    lastDate = date;
    lastCargoType = cargoType;
  }

  @override
  Future<void> importLoad(FreightLoad load) async {
    importLoadCalled = true;
  }

  @override
  Future<Map<String, dynamic>?> evaluateLoad(FreightLoad load) async {
    evaluateLoadCalled = true;
    return {};
  }
}

// ── Test helpers ──────────────────────────────────────────────────────────

Widget wrapScreen({
  _FakeNotifier? notifier,
  FreightExchangeState? initialState,
}) {
  final fake = notifier ?? _FakeNotifier();
  if (initialState != null) {
    fake.manualState = initialState;
  }
  return ProviderScope(
    overrides: [
      freightExchangeStateProvider.overrideWith((ref) => fake),
    ],
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
        DefaultMaterialLocalizations.delegate,
        DefaultWidgetsLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: const FreightExchangeScreen(),
    ),
  );
}

void main() {
  // ==========================================================================
  // Initial state / empty state
  // ==========================================================================
  group('FreightExchangeScreen — initial state', () {
    testWidgets('renders app bar with title', (tester) async {
      await tester.pumpWidget(wrapScreen());
      await tester.pumpAndSettle();
      expect(find.text('Freight Exchange'), findsAtLeastNWidgets(1));
    });

    testWidgets('renders filter bar with four text fields', (tester) async {
      await tester.pumpWidget(wrapScreen());
      await tester.pumpAndSettle();
      expect(find.byType(TextFormField), findsNWidgets(4));
    });

    testWidgets('renders search button', (tester) async {
      await tester.pumpWidget(wrapScreen());
      await tester.pumpAndSettle();
      expect(
        find.widgetWithIcon(ElevatedButton, LucideIcons.search),
        findsOneWidget,
      );
    });

    testWidgets('shows empty state with title and subtitle', (tester) async {
      await tester.pumpWidget(wrapScreen());
      await tester.pumpAndSettle();
      expect(find.text('Freight Exchange'), findsAtLeastNWidgets(1));
      expect(
        find.text(
            'Load board data will appear here when the backend is connected.'),
        findsOneWidget,
      );
    });
  });

  // ==========================================================================
  // Loading state
  // ==========================================================================
  group('FreightExchangeScreen — loading state', () {
    testWidgets('shows circular progress indicator', (tester) async {
      await tester.pumpWidget(wrapScreen(
        initialState: const FreightExchangeLoading(),
      ));
      await tester.pump();
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });
  });

  // ==========================================================================
  // Data state
  // ==========================================================================
  group('FreightExchangeScreen — data state', () {
    testWidgets('renders list of load cards', (tester) async {
      final loads = [
        FreightLoad(
          id: '1',
          providerId: 'p1',
          providerLoadId: 'l1',
          origin: 'Bucharest',
          destination: 'Cluj',
          price: 1200,
          currency: 'EUR',
          weightKg: 15000,
          distanceKm: '400',
        ),
      ];
      await tester.pumpWidget(wrapScreen(
        initialState: FreightExchangeData(loads: loads),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Bucharest'), findsWidgets);
      expect(find.text('Cluj'), findsWidgets);
    });

    testWidgets('tapping a card opens detail bottom sheet', (tester) async {
      final loads = [
        FreightLoad(
          id: '1',
          providerId: 'p1',
          providerLoadId: 'l1',
          origin: 'Bucharest',
          destination: 'Cluj',
        ),
      ];
      await tester.pumpWidget(wrapScreen(
        initialState: FreightExchangeData(loads: loads),
      ));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Bucharest'));
      await tester.pumpAndSettle();
      expect(find.text('Load Details'), findsOneWidget);
      expect(find.text('Import as Trip'), findsOneWidget);
      expect(find.text('Evaluate'), findsOneWidget);
    });

    testWidgets('shows no-loads empty state when list is empty',
        (tester) async {
      await tester.pumpWidget(wrapScreen(
        initialState: const FreightExchangeData(loads: []),
      ));
      await tester.pumpAndSettle();
      expect(find.text('No loads found'), findsOneWidget);
    });
  });

  // ==========================================================================
  // Error state
  // ==========================================================================
  group('FreightExchangeScreen — error state', () {
    testWidgets('shows error empty state', (tester) async {
      await tester.pumpWidget(wrapScreen(
        initialState: const FreightExchangeError(
          messageKey: 'freightExchange_error',
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Failed to load freight data'), findsOneWidget);
    });
  });

  // ==========================================================================
  // Search interactions
  // ==========================================================================
  group('FreightExchangeScreen — search interactions', () {
    testWidgets('tapping search button triggers loadLoads with filters',
        (tester) async {
      final notifier = _FakeNotifier();
      await tester.pumpWidget(wrapScreen(notifier: notifier));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).at(0), 'Bucharest');
      await tester.enterText(find.byType(TextFormField).at(1), 'Cluj');
      await tester.tap(find.widgetWithIcon(ElevatedButton, LucideIcons.search));
      await tester.pumpAndSettle();

      expect(notifier.loadLoadsCalled, true);
      expect(notifier.lastOrigin, 'Bucharest');
      expect(notifier.lastDestination, 'Cluj');
    });
  });
}
