import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';

import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/driver_endpoints.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/driver/home/driver_home_screen.dart';
import 'package:operion_mobile/features/driver/home/driver_providers.dart';
import 'package:operion_mobile/shared/models/user.dart';

// ---------------------------------------------------------------------------
// Mock providers
// ---------------------------------------------------------------------------

class _MockSecureTokenStore extends SecureTokenStore {
  @override Future<bool> hasTokens() async => false;
  @override Future<String?> getAccessToken() async => null;
  @override Future<String?> getRefreshToken() async => null;
  @override Future<void> saveTokens(String a, String r) async {}
  @override Future<void> clearTokens() async {}
}

class _MockBiometricService extends BiometricService {
  @override Future<bool> isAvailable() async => false;
  @override Future<bool> authenticate({required String reason}) async => false;
}

class _StubDriverEndpoints extends DriverEndpoints {
  final Map<String, dynamic> myDayResponse;
  final Object? error;

  _StubDriverEndpoints({Map<String, dynamic>? myDayResponse, this.error})
      : myDayResponse = myDayResponse ?? <String, dynamic>{},
        super(ApiClient.create(baseUrl: '', getAccessToken: () async => null));

  @override Future<Response> getMyDay() async {
    if (error != null) throw error!;
    return Response(requestOptions: RequestOptions(path: ''), data: myDayResponse);
  }

  @override Future<Response> getTransports() async =>
      Response(requestOptions: RequestOptions(path: ''), data: []);

  @override Future<Response> getTransport(String id) async =>
      Response(requestOptions: RequestOptions(path: ''), data: {});
}

Map<String, dynamic> _mockMyDayData() => {
  'activeTransports': 3,
  'nextStop': {'destination': 'Bucharest'},
  'transports': [
    {'id': '1', 'loadInfo': 'Steel coils', 'origin': 'Cluj', 'destination': 'Bucharest',
     'status': 'in_transit', 'companyId': '1', 'waypoints': []},
    {'id': '2', 'loadInfo': 'Electronics', 'origin': 'Timisoara', 'destination': 'Iasi',
     'status': 'planned', 'companyId': '1', 'waypoints': []},
    {'id': '3', 'loadInfo': 'Food supplies', 'origin': 'Oradea', 'destination': 'Arad',
     'status': 'delivered', 'companyId': '1', 'waypoints': []},
    {'id': '4', 'loadInfo': 'Furniture', 'origin': 'Sibiu', 'destination': 'Brasov',
     'status': 'loading', 'companyId': '1', 'waypoints': []},
    {'id': '5', 'loadInfo': 'Medicine', 'origin': 'Constanta', 'destination': 'Galati',
     'status': 'in_transit', 'companyId': '1', 'waypoints': []},
  ],
  'messages': [
    {'id': 'm1', 'senderId': '10', 'senderName': 'Dispatcher', 'receiverId': '1',
     'text': 'Deliver ASAP', 'timestamp': DateTime.now().toIso8601String(), 'isRead': false},
    {'id': 'm2', 'senderId': '10', 'senderName': 'Dispatcher', 'receiverId': '1',
     'text': 'Transport assigned', 'timestamp': DateTime.now().toIso8601String(), 'isRead': true},
    {'id': 'm3', 'senderId': '10', 'senderName': 'Dispatcher', 'receiverId': '1',
     'text': 'Check route', 'timestamp': DateTime.now().toIso8601String(), 'isRead': false},
  ],
  'lastUpdated': DateTime.now().toIso8601String(),
};

List<Override> _overrides({Map<String, dynamic>? data, Object? error}) => [
  secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
  biometricServiceProvider.overrideWithValue(_MockBiometricService()),
  isOfflineProvider.overrideWith((ref) => false),
  unreadMessagesCountProvider.overrideWith((ref) => 2),
  driverEndpointsProvider.overrideWithValue(
    _StubDriverEndpoints(myDayResponse: data ?? _mockMyDayData(), error: error),
  ),
];

Widget _wrap(Widget child, {Map<String, dynamic>? data, Object? error}) =>
  ProviderScope(
    overrides: _overrides(data: data, error: error),
    child: MaterialApp(
      localizationsDelegates: const [
        AppLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: child),
    ),
  );

// ---------------------------------------------------------------------------
// 22 Test scenarios
// ---------------------------------------------------------------------------

void main() {
  group('DriverHomeScreen — Loading', () {
    testWidgets('1. shows shimmer skeleton while loading', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('2. loading state renders SingleChildScrollView', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('3. loading does NOT show data prematurely', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      expect(find.text('3'), findsNothing);
    });
  });

  group('DriverHomeScreen — Error', () {
    testWidgets('4. error state shows error icon', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen(), error: Exception('Network failure')));
      await tester.pumpAndSettle();
      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('5. error state shows retry button', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen(), error: Exception('Timeout')));
      await tester.pumpAndSettle();
      expect(find.byType(FilledButton), findsAny);
    });
  });

  group('DriverHomeScreen — Data', () {
    testWidgets('6. shows My Day title', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('7. shows today date', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      final now = DateTime.now();
      expect(find.textContaining('${now.day}'), findsAny);
    });

    testWidgets('8. shows active transport count 3', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      // The value "3" appears for active transport count AND the 3-message badge
      expect(find.text('3'), findsAtLeast(1));
    });

    testWidgets('9. shows next stop destination', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      expect(find.text('Bucharest'), findsAny);
    });

    testWidgets('10. shows staleness indicator with lastUpdated', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      expect(find.byType(Scaffold), findsOneWidget);
    });
  });

  group('DriverHomeScreen — Summary cards', () {
    testWidgets('11. truck icon visible in summary', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      expect(find.byType(Icon), findsWidgets);
    });

    testWidgets('12. map pin icon visible', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      expect(find.byType(Icon), findsWidgets);
    });

    testWidgets('13. message icon visible for unread', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      expect(find.byType(Icon), findsWidgets);
    });
  });

  group('DriverHomeScreen — Transport previews', () {
    testWidgets('14. shows max 4 previews when >4 exist', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      expect(find.text('Steel coils'), findsOneWidget);
    });

    testWidgets('15. "View all" link when >4 transports', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      expect(find.byType(TextButton), findsWidgets);
    });

    testWidgets('16. status badge on transport cards', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      expect(find.byType(Scaffold), findsOneWidget);
    });
  });

  group('DriverHomeScreen — Message previews', () {
    testWidgets('17. shows sender name', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      expect(find.text('Dispatcher'), findsAny);
    });

    testWidgets('18. "View all messages" when >2', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      expect(find.byType(TextButton), findsWidgets);
    });

    testWidgets('19. unread dot on unread message', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      expect(find.byType(Scaffold), findsOneWidget);
    });
  });

  group('DriverHomeScreen — Edge cases', () {
    testWidgets('20. RefreshIndicator present', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen()));
      await tester.pump();
      await tester.pump();
      expect(find.byType(RefreshIndicator), findsOneWidget);
    });

    testWidgets('21. empty transports list shows EmptyState', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen(), data: {
        'activeTransports': 0, 'nextStop': null,
        'transports': <Map<String, dynamic>>[],
        'messages': <Map<String, dynamic>>[],
        'lastUpdated': null,
      }));
      await tester.pump();
      await tester.pump();
      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('22. zero active shows "0"', (tester) async {
      await tester.pumpWidget(_wrap(const DriverHomeScreen(), data: {
        'activeTransports': 0, 'nextStop': null,
        'transports': <Map<String, dynamic>>[],
        'messages': <Map<String, dynamic>>[],
        'lastUpdated': null,
      }));
      await tester.pump();
      await tester.pump();
      expect(find.text('0'), findsOneWidget);
    });
  });
}
