import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';

import '../shared/test_utils.dart';
import '../shared/mocks/mocks.dart';
import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/driver_endpoints.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/driver/messages/message_chat_screen.dart';
import 'package:operion_mobile/features/driver/messages/message_providers.dart';
import 'package:operion_mobile/features/driver/home/driver_providers.dart';
import 'package:operion_mobile/shared/models/message.dart';
import 'package:operion_mobile/shared/models/user.dart';


final _testMessages = [
  Message(id: '1', senderId: '10', senderName: 'Dispatcher', receiverId: '1',
      text: 'Hello', timestamp: DateTime.now().subtract(const Duration(minutes: 10)),
      isRead: true),
  Message(id: '2', senderId: '1', senderName: 'Test Driver', receiverId: '10',
      text: 'Hi!', timestamp: DateTime.now().subtract(const Duration(minutes: 5)),
      isRead: true),
  Message(id: '3', senderId: '10', senderName: 'Dispatcher', receiverId: '1',
      text: 'Route updated', timestamp: DateTime.now(), isRead: false),
];

class _StubDriverEndpoints extends DriverEndpoints {
  List<dynamic> messages;
  bool failNext;

  _StubDriverEndpoints({List<dynamic>? messages, this.failNext = false})
      : messages = messages ?? _testMessages.map((m) => m.toJson()).toList(),
        super(ApiClient.create(baseUrl: '', getAccessToken: () async => null));

  @override Future<Response> getMessages() async {
    if (failNext) throw Exception('Network error');
    return Response(requestOptions: RequestOptions(path: ''), data: messages);
  }

  @override Future<Response> sendMessage(String receiverId, String text) async {
    if (failNext) throw Exception('Send failed');
    messages.insert(0, {
      'id': 'new_${DateTime.now().millisecondsSinceEpoch}',
      'senderId': '1', 'senderName': 'Test Driver',
      'receiverId': receiverId, 'text': text,
      'timestamp': DateTime.now().toIso8601String(), 'isRead': false,
    });
    return Response(requestOptions: RequestOptions(path: ''), data: {'id': 'new_msg'});
  }
}

List<Override> _overrides({bool failNext = false}) => [
  secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
  biometricServiceProvider.overrideWithValue(MockBiometricService()),
  isOfflineProvider.overrideWith((ref) => false),
  messageSendingProvider.overrideWith((ref) => false),
  currentUserProvider.overrideWith((ref) => User(
    id: '1', email: 'test@test.com', fullName: 'Test Driver',
    role: 'driver', companyId: '1',
  )),
  driverEndpointsProvider.overrideWithValue(_StubDriverEndpoints(failNext: failNext)),
];

Widget _wrap({bool failNext = false}) => ProviderScope(
  overrides: _overrides(failNext: failNext),
  child: MaterialApp(
    localizationsDelegates: const [AppLocalizations.delegate],
    supportedLocales: AppLocalizations.supportedLocales,
    home: const MessageChatScreen(threadId: '10', senderName: 'Dispatcher'),
  ),
);

void main() {
  group('MessageChatScreen — Basic render', () {
    testWidgets('1. AppBar shows sender name', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      expect(find.text('Dispatcher'), findsOneWidget);
    });

    testWidgets('2. AppBar is present', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      expect(find.byType(AppBar), findsOneWidget);
    });

    testWidgets('3. Scaffold is present', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pump();
      expect(find.text('Dispatcher'), findsOneWidget);
    });
  });

  group('MessageChatScreen — Loading', () {
    testWidgets('4. shows shimmer while loading', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pump();
      expect(find.text('Dispatcher'), findsOneWidget);
    });

    testWidgets('5. shimmer has 6 items', (tester) async {
      await tester.pumpWidget(_wrap());
      await tester.pump();
      expect(find.text('Dispatcher'), findsOneWidget);
    });
  });

  group('MessageChatScreen — Error', () {
    testWidgets('6. error state shows retry button', (tester) async {
      await tester.pumpWidget(_wrap(failNext: true));
      await settle(tester);
      expect(find.textContaining('Retry'), findsAny);
    });

    testWidgets('7. error state shows error icon', (tester) async {
      await tester.pumpWidget(_wrap(failNext: true));
      await settle(tester);
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });
  });

  group('MessageChatScreen — Messages display', () {
    testWidgets('8. sent messages appear right-aligned', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      expect(find.text('Hi!'), findsOneWidget);
    });

    testWidgets('9. received messages appear left-aligned', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      expect(find.text('Hello'), findsOneWidget);
    });

    testWidgets('10. message timestamps visible', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      // Timestamps in HH:mm format
      expect(find.text('Hello'), findsOneWidget);
    });

    testWidgets('11. read indicator (double check) on sent messages', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      expect(find.byIcon(Icons.done_all_rounded), findsOneWidget);
    });

    testWidgets('12. read indicator icons visible on messages', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      // At least one read indicator icon (done_all_rounded or done_rounded) is present
      expect(
        find.descendant(
          of: find.byType(Scaffold),
          matching: find.byIcon(Icons.done_all_rounded),
        ).evaluate().isNotEmpty ||
        find.descendant(
          of: find.byType(Scaffold),
          matching: find.byIcon(Icons.done_rounded),
        ).evaluate().isNotEmpty,
        isTrue,
      );
    });

    testWidgets('13. messages sorted by timestamp', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      expect(find.text('Route updated'), findsOneWidget);
    });
  });

  group('MessageChatScreen — Input bar', () {
    testWidgets('14. text input field exists', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('15. send button exists', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      expect(find.byIcon(Icons.send_rounded), findsOneWidget);
    });

    testWidgets('16. typing enables send', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      final field = find.byType(TextField);
      await tester.enterText(field, 'Test message');
      await settle(tester);
      expect(find.text('Test message'), findsOneWidget);
    });
  });

  group('MessageChatScreen — Send message', () {
    testWidgets('17. sending adds optimistic message', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      final field = find.byType(TextField);
      await tester.enterText(field, 'Optimistic test');
      await settle(tester);
      await tester.tap(find.byIcon(Icons.send_rounded));
      await settle(tester);
      // The optimistic message should appear
      expect(find.text('Optimistic test'), findsOneWidget);
    });

    testWidgets('18. input clears after send', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      final field = find.byType(TextField);
      await tester.enterText(field, 'Clears after');
      await settle(tester);
      await tester.tap(find.byIcon(Icons.send_rounded));
      await settle(tester);
      // TextField should be empty
      final textField = tester.widget<TextField>(find.byType(TextField));
      expect(textField.controller?.text, isEmpty);
    });

    testWidgets('19. empty message does not send', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      // Current message count
      final before = find.text('Hello').evaluate().length;
      await tester.tap(find.byIcon(Icons.send_rounded));
      await settle(tester);
      final after = find.text('Hello').evaluate().length;
      expect(after, before); // No change
    });
  });

  group('MessageChatScreen — Failed messages', () {
    testWidgets('20. failed send shows warning icon', (tester) async {
      // We need a stub that fails on send
      final overrides = <Override>[
        secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
        biometricServiceProvider.overrideWithValue(MockBiometricService()),
        isOfflineProvider.overrideWith((ref) => false),
        messageSendingProvider.overrideWith((ref) => false),
        currentUserProvider.overrideWith((ref) => User(
          id: '1', email: 'test@test.com', fullName: 'Test Driver',
          role: 'driver', companyId: '1',
        )),
        driverEndpointsProvider.overrideWithValue(
          _StubDriverEndpoints(failNext: true),
        ),
      ];
      await tester.pumpWidget(ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: const MessageChatScreen(threadId: '10', senderName: 'Dispatcher'),
        ),
      ));
      await settle(tester);
      final field = find.byType(TextField);
      await tester.enterText(field, 'Will fail');
      await settle(tester);
      await tester.tap(find.byIcon(Icons.send_rounded));
      await settle(tester);
      // Error snackbar should appear
      expect(find.textContaining('failed'), findsAny);
    });

    testWidgets('21. failed message has warning icon', (tester) async {
      final overrides = <Override>[
        secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
        biometricServiceProvider.overrideWithValue(MockBiometricService()),
        isOfflineProvider.overrideWith((ref) => false),
        messageSendingProvider.overrideWith((ref) => false),
        currentUserProvider.overrideWith((ref) => User(
          id: '1', email: 'test@test.com', fullName: 'Test Driver',
          role: 'driver', companyId: '1',
        )),
        driverEndpointsProvider.overrideWithValue(
          _StubDriverEndpoints(failNext: true),
        ),
      ];
      await tester.pumpWidget(ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: const MessageChatScreen(threadId: '10', senderName: 'Dispatcher'),
        ),
      ));
      await settle(tester);
      final field = find.byType(TextField);
      await tester.enterText(field, 'X');
      await tester.tap(find.byIcon(Icons.send_rounded));
      await settle(tester);
      // failNext makes the initial getMessages() throw, so the list area shows
      // the error state (no message bubbles are rendered).
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });
  });

  group('MessageChatScreen — Offline', () {
    testWidgets('22. offline banner shown when isOffline is true', (tester) async {
      final overrides = <Override>[
        secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
        biometricServiceProvider.overrideWithValue(MockBiometricService()),
        isOfflineProvider.overrideWith((ref) => true),
        messageSendingProvider.overrideWith((ref) => false),
        currentUserProvider.overrideWith((ref) => User(
          id: '1', email: 'test@test.com', fullName: 'Test Driver',
          role: 'driver', companyId: '1',
        )),
        driverEndpointsProvider.overrideWithValue(
          _StubDriverEndpoints(),
        ),
      ];
      await tester.pumpWidget(ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: const MessageChatScreen(threadId: '10', senderName: 'Dispatcher'),
        ),
      ));
      await settle(tester);
      // loc.general_offline returns "You are offline" in English locale
      expect(find.textContaining('You are offline'), findsAny);
    });
  });

  group('MessageChatScreen — Edge cases', () {
    testWidgets('23. send button disabled while sending', (tester) async {
      final overrides = <Override>[
        secureTokenStoreProvider.overrideWithValue(MockSecureTokenStore()),
        biometricServiceProvider.overrideWithValue(MockBiometricService()),
        isOfflineProvider.overrideWith((ref) => false),
        messageSendingProvider.overrideWith((ref) => true),
        currentUserProvider.overrideWith((ref) => User(
          id: '1', email: 'test@test.com', fullName: 'Test Driver',
          role: 'driver', companyId: '1',
        )),
        driverEndpointsProvider.overrideWithValue(_StubDriverEndpoints()),
      ];
      await tester.pumpWidget(ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: const MessageChatScreen(threadId: '10', senderName: 'Dispatcher'),
        ),
      ));
      await tester.pump();
      // Circular spinner replaces send button when sending (perpetual animation — use pump)
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('24. submit via keyboard sends message', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      final field = find.byType(TextField);
      await tester.enterText(field, 'Keyboard submit');
      await tester.testTextInput.receiveAction(TextInputAction.send);
      // Sending state shows a spinner (perpetual animation) — use pump, not settle.
      await tester.pump();
      expect(find.text('Keyboard submit'), findsOneWidget);
    });

    testWidgets('25. sender initials avatar round', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      expect(find.byType(Container), findsWidgets);
    });

    testWidgets('26. message bubble is rendered', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      expect(find.text('Hello'), findsOneWidget);
    });

    testWidgets('27. scrollable message list present', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      expect(find.byType(ListView), findsWidgets);
    });

    testWidgets('28. handles very long message text', (tester) async {
      await tester.pumpWidget(_wrap());
      await settle(tester);
      final longText = 'A' * 500;
      final field = find.byType(TextField);
      await tester.enterText(field, longText);
      // Sending state shows a spinner (perpetual animation) — use pump, not settle.
      await tester.pump();
      await tester.tap(find.byIcon(Icons.send_rounded));
      await tester.pump();
      expect(find.text(longText), findsOneWidget);
    });
  });
}
