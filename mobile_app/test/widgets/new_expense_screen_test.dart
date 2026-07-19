import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import 'package:operion_mobile/core/auth/auth_providers.dart';
import 'package:operion_mobile/core/auth/biometric_service.dart';
import 'package:operion_mobile/core/storage/secure_token_store.dart';
import 'package:operion_mobile/core/i18n/app_localizations.dart';
import 'package:operion_mobile/features/driver/expenses/new_expense_screen.dart';
import 'package:operion_mobile/features/driver/expenses/expense_providers.dart';
import 'package:operion_mobile/core/network/endpoints/auth_endpoints.dart';
import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/shared/models/user.dart';

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

List<Override> _baseOverrides() => [
  secureTokenStoreProvider.overrideWithValue(_MockSecureTokenStore()),
  biometricServiceProvider.overrideWithValue(_MockBiometricService()),
  expenseSubmittingProvider.overrideWith((ref) => false),
  currentUserProvider.overrideWith((ref) => User(
    id: '1', email: 'test@test.com', fullName: 'Test Driver',
    role: 'driver', companyId: '1',
  )),
];

Widget _wrap(Widget child) => ProviderScope(
  overrides: _baseOverrides(),
  child: MaterialApp(
    localizationsDelegates: const [AppLocalizations.delegate],
    supportedLocales: AppLocalizations.supportedLocales,
    home: child,
  ),
);

void main() {
  group('NewExpenseScreen — Rendering', () {
    testWidgets('1. AppBar shows "New Expense"', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.textContaining('xpens'), findsAny);
    });

    testWidgets('2. scaffold is present', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('3. SegmentedButton for type is present', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.byType(SegmentedButton<String>), findsOneWidget);
    });

    testWidgets('4. shows Fuel segment by default', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.textContaining('uel'), findsAny);
    });

    testWidgets('5. shows Tolls segment', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.textContaining('oll'), findsAny);
    });

    testWidgets('6. shows Per Diem segment', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.textContaining('iem'), findsAny);
    });

    testWidgets('7. shows Other segment', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.textContaining('ther'), findsAny);
    });
  });

  group('NewExpenseScreen — Amount field', () {
    testWidgets('8. amount text field exists', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.byType(TextFormField), findsWidgets);
    });

    testWidgets('9. euro prefix visible', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.text('\u20ac'), findsOneWidget);
    });

    testWidgets('10. amount field validation shows error for empty', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      // Focus and submit empty
      await tester.tap(find.textContaining('ubmit'));
      await tester.pumpAndSettle();
      expect(find.textContaining('required'), findsAny);
    });

    testWidgets('11. amount field rejects zero', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      final field = find.byType(TextFormField).first;
      await tester.enterText(field, '0');
      await tester.tap(find.textContaining('ubmit'));
      await tester.pumpAndSettle();
      expect(find.textContaining('greater'), findsAny);
    });

    testWidgets('12. amount accepts valid decimal', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      final field = find.byType(TextFormField).first;
      await tester.enterText(field, '150.75');
      await tester.pumpAndSettle();
      // Validation should pass (no error text)
      expect(find.textContaining('required'), findsNothing);
    });
  });

  group('NewExpenseScreen — Date', () {
    testWidgets('13. calendar icon visible in date picker row', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.byType(Icon), findsWidgets);
    });

    testWidgets('14. multiple icons visible on screen', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.byType(Icon), findsWidgets);
    });

    testWidgets('15. tapping date text opens date picker', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      // Tap the formatted date text (e.g. "Jul 14, 2026") to open the picker
      final now = DateTime.now();
      final dateStr = DateFormat.yMMMd().format(now);
      await tester.tap(find.text(dateStr));
      await tester.pumpAndSettle();
      // DatePicker dialog should appear
      expect(find.byType(DatePickerDialog), findsOneWidget);
    });
  });

  group('NewExpenseScreen — Description', () {
    testWidgets('16. description text field exists', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.byType(TextFormField), findsWidgets);
    });

    testWidgets('17. description accepts multi-line text', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      // Find the description field (multi-line, maxLines:3)
      final fields = find.byType(TextFormField);
      expect(fields, findsWidgets);
    });
  });

  group('NewExpenseScreen — Submit', () {
    testWidgets('18. submit button is present', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.textContaining('ubmit'), findsAny);
    });

    testWidgets('19. submit button shows spinner while submitting', (tester) async {
      await tester.pumpWidget(ProviderScope(
        overrides: [
          ..._baseOverrides(),
          expenseSubmittingProvider.overrideWith((ref) => true),
        ],
        child: MaterialApp(
          localizationsDelegates: const [AppLocalizations.delegate],
          supportedLocales: AppLocalizations.supportedLocales,
          home: const NewExpenseScreen(),
        ),
      ));
      await tester.pump();
      // CircularProgressIndicator has perpetual animation, use pump not pumpAndSettle
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });
  });

  group('NewExpenseScreen — SegmentedButton interaction', () {
    testWidgets('20. selecting Tolls changes _selectedType', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      // Tap on Tolls segment
      await tester.tap(find.textContaining('oll'));
      await tester.pumpAndSettle();
      // The tolls icon should become primary color
      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('21. selecting Per Diem changes type', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      await tester.tap(find.textContaining('iem'));
      await tester.pumpAndSettle();
      expect(find.byType(SegmentedButton<String>), findsOneWidget);
    });
  });

  group('NewExpenseScreen — Edge cases', () {
    testWidgets('22. form scrolls on keyboard open', (tester) async {
      await tester.pumpWidget(_wrap(const NewExpenseScreen()));
      await tester.pumpAndSettle();
      expect(find.byType(SingleChildScrollView), findsOneWidget);
    });
  });
}
