import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/shared/models/sync_cursor.dart';

void main() {
  group('SyncCursor', () {
    // ---------------------------------------------------------------------------
    // fromJson
    // ---------------------------------------------------------------------------
    group('fromJson', () {
      test('parses valid JSON correctly', () {
        final json = {
          'lastSyncTimestamp': '2024-06-15T10:30:00.000Z',
          'entityType': 'transport',
        };
        final cursor = SyncCursor.fromJson(json);
        expect(cursor.lastSyncTimestamp, DateTime.utc(2024, 6, 15, 10, 30));
        expect(cursor.entityType, 'transport');
      });

      test('handles null values with defaults', () {
        final json = <String, dynamic>{
          'lastSyncTimestamp': null,
          'entityType': null,
        };
        final cursor = SyncCursor.fromJson(json);
        expect(cursor.lastSyncTimestamp, isA<DateTime>());
        expect(cursor.entityType, '');
      });

      test('handles missing keys with defaults', () {
        final cursor = SyncCursor.fromJson(<String, dynamic>{});
        expect(cursor.lastSyncTimestamp, isA<DateTime>());
        expect(cursor.entityType, '');
      });

      test('handles wrong types gracefully', () {
        // `as String?` on int throws TypeError at runtime
        expect(
          () => SyncCursor.fromJson({
            'entityType': 123,
          }),
          throwsA(isA<TypeError>()),
        );
      });

      test('parses DateTime from int milliseconds', () {
        final ms = DateTime.utc(2024, 6, 15, 14, 30).millisecondsSinceEpoch;
        final json = {
          'lastSyncTimestamp': ms,
          'entityType': 'driver',
        };
        final cursor = SyncCursor.fromJson(json);
        expect(
          cursor.lastSyncTimestamp,
          DateTime.fromMillisecondsSinceEpoch(ms),
        );
      });

      test('parses DateTime from int seconds', () {
        final seconds =
            DateTime.utc(2024, 6, 15).millisecondsSinceEpoch ~/ 1000;
        final json = {
          'lastSyncTimestamp': seconds,
          'entityType': 'expense',
        };
        final cursor = SyncCursor.fromJson(json);
        expect(
          cursor.lastSyncTimestamp,
          DateTime.fromMillisecondsSinceEpoch(seconds * 1000),
        );
      });

      test('parses DateTime from ISO string', () {
        final json = {
          'lastSyncTimestamp': '2024-12-01T08:00:00.000Z',
          'entityType': 'message',
        };
        final cursor = SyncCursor.fromJson(json);
        expect(cursor.lastSyncTimestamp, DateTime.utc(2024, 12, 1, 8, 0));
      });

      test('handles empty entityType string', () {
        final json = {
          'lastSyncTimestamp': '2024-01-01T00:00:00.000',
          'entityType': '',
        };
        final cursor = SyncCursor.fromJson(json);
        expect(cursor.entityType, '');
      });
    });

    // ---------------------------------------------------------------------------
    // toJson
    // ---------------------------------------------------------------------------
    group('toJson', () {
      test('produces correct map', () {
        final cursor = SyncCursor(
          lastSyncTimestamp: DateTime.utc(2024, 6, 15, 10, 30),
          entityType: 'transport',
        );
        final json = cursor.toJson();
        expect(json['lastSyncTimestamp'], '2024-06-15T10:30:00.000Z');
        expect(json['entityType'], 'transport');
      });

      test('round-trip fromJson → toJson produces same map', () {
        final original = {
          'lastSyncTimestamp': '2024-07-20T12:00:00.000Z',
          'entityType': 'document',
        };
        final cursor = SyncCursor.fromJson(original);
        final output = cursor.toJson();
        expect(output['lastSyncTimestamp'], '2024-07-20T12:00:00.000Z');
        expect(output['entityType'], 'document');
      });
    });

    // ---------------------------------------------------------------------------
    // copyWith
    // ---------------------------------------------------------------------------
    group('copyWith', () {
      test('returns same object when no arguments', () {
        final cursor = SyncCursor(
          lastSyncTimestamp: DateTime.utc(2024, 1, 1),
          entityType: 'transport',
        );
        expect(cursor.copyWith(), cursor);
      });

      test('overrides specified fields', () {
        final cursor = SyncCursor(
          lastSyncTimestamp: DateTime.utc(2024, 1, 1),
          entityType: 'transport',
        );
        final copy = cursor.copyWith(
          lastSyncTimestamp: DateTime.utc(2024, 6, 15),
          entityType: 'expense',
        );
        expect(copy.lastSyncTimestamp, DateTime.utc(2024, 6, 15));
        expect(copy.entityType, 'expense');
      });
    });

    // ---------------------------------------------------------------------------
    // Equality
    // ---------------------------------------------------------------------------
    group('equality', () {
      test('same values are equal', () {
        final a = SyncCursor(
          lastSyncTimestamp: DateTime.utc(2024, 1, 1),
          entityType: 'transport',
        );
        final b = SyncCursor(
          lastSyncTimestamp: DateTime.utc(2024, 1, 1),
          entityType: 'transport',
        );
        expect(a, b);
        expect(a.hashCode, b.hashCode);
      });

      test('different entity types are not equal', () {
        final a = SyncCursor(
          lastSyncTimestamp: DateTime.utc(2024, 1, 1),
          entityType: 'transport',
        );
        final b = SyncCursor(
          lastSyncTimestamp: DateTime.utc(2024, 1, 1),
          entityType: 'expense',
        );
        expect(a, isNot(b));
      });
    });

    // ---------------------------------------------------------------------------
    // toString
    // ---------------------------------------------------------------------------
    group('toString', () {
      test('includes key fields', () {
        final cursor = SyncCursor(
          lastSyncTimestamp: DateTime.utc(2024, 1, 1),
          entityType: 'transport',
        );
        final str = cursor.toString();
        expect(str, contains('transport'));
        expect(str, contains('2024'));
      });
    });
  });
}
