import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/shared/models/expense.dart';

void main() {
  group('Expense', () {
    // ---------------------------------------------------------------------------
    // fromJson
    // ---------------------------------------------------------------------------
    group('fromJson', () {
      test('parses valid JSON correctly', () {
        final json = {
          'id': 'exp-1',
          'driverId': 'driver-1',
          'transportId': 'tr-42',
          'type': 'fuel',
          'amount': 450.75,
          'currency': 'EUR',
          'date': '2024-06-15T10:30:00.000Z',
          'receiptImageUrl': 'https://example.com/receipt.jpg',
          'status': 'approved',
          'notes': 'Full tank at OMV',
        };
        final expense = Expense.fromJson(json);
        expect(expense.id, 'exp-1');
        expect(expense.driverId, 'driver-1');
        expect(expense.transportId, 'tr-42');
        expect(expense.type, 'fuel');
        expect(expense.amount, 450.75);
        expect(expense.currency, 'EUR');
        expect(expense.date, DateTime.utc(2024, 6, 15, 10, 30));
        expect(expense.receiptImageUrl, 'https://example.com/receipt.jpg');
        expect(expense.status, 'approved');
        expect(expense.notes, 'Full tank at OMV');
      });

      test('handles null values with defaults', () {
        final json = <String, dynamic>{
          'id': null,
          'driverId': null,
          'transportId': null,
          'type': null,
          'amount': null,
          'currency': null,
          'date': null,
          'receiptImageUrl': null,
          'status': null,
          'notes': null,
        };
        final expense = Expense.fromJson(json);
        expect(expense.id, '');
        expect(expense.driverId, '');
        expect(expense.transportId, isNull);
        expect(expense.type, '');
        expect(expense.amount, 0.0);
        expect(expense.currency, 'RON');
        expect(expense.date, isA<DateTime>());
        expect(expense.receiptImageUrl, isNull);
        expect(expense.status, 'pending');
        expect(expense.notes, isNull);
      });

      test('handles missing keys with defaults', () {
        final expense = Expense.fromJson(<String, dynamic>{});
        expect(expense.id, '');
        expect(expense.amount, 0.0);
        expect(expense.currency, 'RON');
        expect(expense.status, 'pending');
        expect(expense.transportId, isNull);
        expect(expense.notes, isNull);
      });

      test('handles wrong types gracefully', () {
        // `as String?` on int/bool throws TypeError at runtime
        expect(
          () => Expense.fromJson({
            'id': 123,
            'driverId': true,
            'transportId': 456,
            'type': null,
            'amount': 'notanumber',
            'currency': 1,
          }),
          throwsA(isA<TypeError>()),
        );
      });

      test('parses amount from int', () {
        final json = {
          'id': 'e',
          'driverId': 'd',
          'type': 'fuel',
          'amount': 100,
          'date': '2024-01-01T00:00:00.000',
        };
        final expense = Expense.fromJson(json);
        expect(expense.amount, 100.0);
      });

      test('parses negative amount', () {
        final json = {
          'id': 'e',
          'driverId': 'd',
          'type': 'fuel',
          'amount': -50.0,
          'date': '2024-01-01T00:00:00.000',
        };
        final expense = Expense.fromJson(json);
        expect(expense.amount, -50.0);
      });

      test('parses very large amount', () {
        final json = {
          'id': 'e',
          'driverId': 'd',
          'type': 'fuel',
          'amount': 9999999.99,
          'date': '2024-01-01T00:00:00.000',
        };
        final expense = Expense.fromJson(json);
        expect(expense.amount, 9999999.99);
      });

      test('parses DateTime from int milliseconds', () {
        final ms = DateTime.utc(2024, 6, 15).millisecondsSinceEpoch;
        final json = {
          'id': 'e',
          'driverId': 'd',
          'type': 'fuel',
          'amount': 10.0,
          'date': ms,
        };
        final expense = Expense.fromJson(json);
        expect(
          expense.date,
          DateTime.fromMillisecondsSinceEpoch(ms),
        );
      });

      test('parses DateTime from int seconds', () {
        final seconds = DateTime.utc(2024, 6, 15).millisecondsSinceEpoch ~/ 1000;
        final json = {
          'id': 'e',
          'driverId': 'd',
          'type': 'fuel',
          'amount': 10.0,
          'date': seconds,
        };
        final expense = Expense.fromJson(json);
        expect(
          expense.date,
          DateTime.fromMillisecondsSinceEpoch(seconds * 1000),
        );
      });

      test('parses DateTime from ISO string', () {
        final json = {
          'id': 'e',
          'driverId': 'd',
          'type': 'fuel',
          'amount': 10.0,
          'date': '2024-12-25T08:00:00.000Z',
        };
        final expense = Expense.fromJson(json);
        expect(expense.date, DateTime.utc(2024, 12, 25, 8, 0));
      });

      test('handles empty strings', () {
        final json = {
          'id': '',
          'driverId': '',
          'type': '',
          'amount': 0.0,
          'currency': '',
          'date': '2024-01-01T00:00:00.000',
          'status': '',
        };
        final expense = Expense.fromJson(json);
        expect(expense.id, '');
        expect(expense.type, '');
        expect(expense.currency, '');
        expect(expense.status, '');
      });
    });

    // ---------------------------------------------------------------------------
    // toJson
    // ---------------------------------------------------------------------------
    group('toJson', () {
      test('produces correct map', () {
        final expense = Expense(
          id: 'exp-1',
          driverId: 'driver-1',
          transportId: 'tr-42',
          type: 'fuel',
          amount: 450.75,
          currency: 'EUR',
          date: DateTime.utc(2024, 6, 15, 10, 30),
          receiptImageUrl: 'https://example.com/receipt.jpg',
          status: 'approved',
          notes: 'Full tank',
        );
        final json = expense.toJson();
        expect(json['id'], 'exp-1');
        expect(json['driverId'], 'driver-1');
        expect(json['transportId'], 'tr-42');
        expect(json['type'], 'fuel');
        expect(json['amount'], 450.75);
        expect(json['currency'], 'EUR');
        expect(json['date'], '2024-06-15T10:30:00.000Z');
        expect(json['receiptImageUrl'], 'https://example.com/receipt.jpg');
        expect(json['status'], 'approved');
        expect(json['notes'], 'Full tank');
      });

      test('round-trip fromJson → toJson produces same map', () {
        final original = {
          'id': 'rt-1',
          'driverId': 'd-1',
          'transportId': null,
          'type': 'tolls',
          'amount': 35.5,
          'currency': 'RON',
          'date': '2024-08-10T12:00:00.000Z',
          'receiptImageUrl': null,
          'status': 'pending',
          'notes': null,
        };
        final expense = Expense.fromJson(original);
        final output = expense.toJson();
        expect(output['id'], 'rt-1');
        expect(output['driverId'], 'd-1');
        expect(output['transportId'], isNull);
        expect(output['type'], 'tolls');
        expect(output['amount'], 35.5);
        expect(output['currency'], 'RON');
        expect(output['date'], '2024-08-10T12:00:00.000Z');
        expect(output['receiptImageUrl'], isNull);
        expect(output['status'], 'pending');
        expect(output['notes'], isNull);
      });

      test('omits null optional fields', () {
        final expense = Expense(
          id: 'e',
          driverId: 'd',
          type: 'other',
          amount: 0.0,
          date: DateTime.utc(2024, 1, 1),
        );
        final json = expense.toJson();
        expect(json['transportId'], isNull);
        expect(json['receiptImageUrl'], isNull);
        expect(json['notes'], isNull);
      });
    });

    // ---------------------------------------------------------------------------
    // copyWith
    // ---------------------------------------------------------------------------
    group('copyWith', () {
      test('returns same object when no arguments', () {
        final expense = Expense(
          id: 'e',
          driverId: 'd',
          type: 'fuel',
          amount: 100.0,
          date: DateTime.utc(2024, 1, 1),
        );
        expect(expense.copyWith(), expense);
      });

      test('overrides specified fields', () {
        final expense = Expense(
          id: 'e',
          driverId: 'd',
          type: 'fuel',
          amount: 100.0,
          date: DateTime.utc(2024, 1, 1),
        );
        final copy = expense.copyWith(
          amount: 200.0,
          status: 'approved',
          notes: 'Updated',
        );
        expect(copy.amount, 200.0);
        expect(copy.status, 'approved');
        expect(copy.notes, 'Updated');
        expect(copy.id, 'e');
      });
    });

    // ---------------------------------------------------------------------------
    // Equality
    // ---------------------------------------------------------------------------
    group('equality', () {
      test('same values are equal', () {
        final a = Expense(
          id: 'e1',
          driverId: 'd1',
          type: 'fuel',
          amount: 100.0,
          date: DateTime.utc(2024, 1, 1),
        );
        final b = Expense(
          id: 'e1',
          driverId: 'd1',
          type: 'fuel',
          amount: 100.0,
          date: DateTime.utc(2024, 1, 1),
        );
        expect(a, b);
        expect(a.hashCode, b.hashCode);
      });

      test('different amounts are not equal', () {
        final a = Expense(
          id: 'e1',
          driverId: 'd1',
          type: 'fuel',
          amount: 100.0,
          date: DateTime.utc(2024, 1, 1),
        );
        final b = Expense(
          id: 'e1',
          driverId: 'd1',
          type: 'fuel',
          amount: 200.0,
          date: DateTime.utc(2024, 1, 1),
        );
        expect(a, isNot(b));
      });
    });

    // ---------------------------------------------------------------------------
    // toString
    // ---------------------------------------------------------------------------
    group('toString', () {
      test('includes key fields', () {
        final expense = Expense(
          id: 'exp-1',
          driverId: 'd-1',
          type: 'fuel',
          amount: 450.75,
          currency: 'RON',
          date: DateTime.utc(2024, 1, 1),
        );
        final str = expense.toString();
        expect(str, contains('exp-1'));
        expect(str, contains('fuel'));
        expect(str, contains('450.75'));
        expect(str, contains('RON'));
      });
    });
  });
}
