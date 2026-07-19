import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/shared/models/alert.dart';

void main() {
  group('Alert', () {
    // ---------------------------------------------------------------------------
    // fromJson – valid JSON
    // ---------------------------------------------------------------------------
    group('fromJson', () {
      test('parses valid JSON correctly', () {
        final json = {
          'id': 'alert-1',
          'companyId': 'comp-1',
          'type': 'maintenance',
          'title': 'Oil change due',
          'description': 'Change oil for truck #42',
          'severity': 'high',
          'isRead': true,
          'createdAt': '2024-06-15T10:30:00.000Z',
          'relatedEntityId': 'vehicle-42',
          'relatedEntityType': 'vehicle',
        };
        final alert = Alert.fromJson(json);
        expect(alert.id, 'alert-1');
        expect(alert.companyId, 'comp-1');
        expect(alert.type, 'maintenance');
        expect(alert.title, 'Oil change due');
        expect(alert.description, 'Change oil for truck #42');
        expect(alert.severity, 'high');
        expect(alert.isRead, true);
        expect(alert.createdAt, DateTime.utc(2024, 6, 15, 10, 30));
        expect(alert.relatedEntityId, 'vehicle-42');
        expect(alert.relatedEntityType, 'vehicle');
      });

      test('handles null values with defaults', () {
        final json = <String, dynamic>{
          'id': null,
          'companyId': null,
          'type': null,
          'title': null,
          'description': null,
          'severity': null,
          'isRead': null,
          'createdAt': null,
          'relatedEntityId': null,
          'relatedEntityType': null,
        };
        final alert = Alert.fromJson(json);
        // String fields default to ''
        expect(alert.id, '');
        expect(alert.companyId, '');
        expect(alert.type, '');
        expect(alert.title, '');
        expect(alert.description, '');
        // severity defaults to 'medium', isRead defaults to false
        expect(alert.severity, 'medium');
        expect(alert.isRead, false);
        // createdAt fallback returns DateTime.now() on null
        expect(alert.createdAt, isA<DateTime>());
        // Nullable fields are null
        expect(alert.relatedEntityId, isNull);
        expect(alert.relatedEntityType, isNull);
      });

      test('handles missing keys with defaults', () {
        final json = <String, dynamic>{};
        final alert = Alert.fromJson(json);
        expect(alert.id, '');
        expect(alert.companyId, '');
        expect(alert.type, '');
        expect(alert.title, '');
        expect(alert.description, '');
        expect(alert.severity, 'medium');
        expect(alert.isRead, false);
        expect(alert.createdAt, isA<DateTime>());
        expect(alert.relatedEntityId, isNull);
        expect(alert.relatedEntityType, isNull);
      });

      test('handles wrong types gracefully', () {
        // `as String?` on int/bool throws TypeError at runtime
        expect(
          () => Alert.fromJson({
            'id': 123,
            'companyId': true,
            'type': 45.6,
            'title': null,
            'description': ['desc'],
            'severity': 1,
            'isRead': 'notabool',
          }),
          throwsA(isA<TypeError>()),
        );
      });

      test('parses DateTime from int milliseconds', () {
        final ms = DateTime.utc(2024, 1, 15, 10, 30).millisecondsSinceEpoch;
        final json = {
          'id': 'a',
          'companyId': 'c',
          'type': 't',
          'title': 'T',
          'description': 'D',
          'createdAt': ms,
        };
        final alert = Alert.fromJson(json);
        expect(
          alert.createdAt,
          DateTime.fromMillisecondsSinceEpoch(ms),
        );
      });

      test('parses DateTime from int seconds', () {
        // value <= 1e12 → treated as seconds and multiplied by 1000
        final seconds = DateTime.utc(2024, 6, 15).millisecondsSinceEpoch ~/ 1000;
        final json = {
          'id': 'a',
          'companyId': 'c',
          'type': 't',
          'title': 'T',
          'description': 'D',
          'createdAt': seconds,
        };
        final alert = Alert.fromJson(json);
        expect(
          alert.createdAt,
          DateTime.fromMillisecondsSinceEpoch(seconds * 1000),
        );
      });

      test('parses DateTime from ISO string', () {
        final json = {
          'id': 'a',
          'companyId': 'c',
          'type': 't',
          'title': 'T',
          'description': 'D',
          'createdAt': '2024-12-01T08:00:00.000Z',
        };
        final alert = Alert.fromJson(json);
        expect(alert.createdAt, DateTime.utc(2024, 12, 1, 8, 0));
      });

      test('handles empty strings in fields', () {
        final json = {
          'id': '',
          'companyId': '',
          'type': '',
          'title': '',
          'description': '',
          'severity': '',
          'isRead': false,
          'createdAt': '2024-01-01T00:00:00.000',
        };
        final alert = Alert.fromJson(json);
        expect(alert.id, '');
        expect(alert.type, '');
        expect(alert.severity, ''); // empty string overrides 'medium' default
        expect(alert.isRead, false);
      });
    });

    // ---------------------------------------------------------------------------
    // toJson
    // ---------------------------------------------------------------------------
    group('toJson', () {
      test('produces correct map', () {
        final alert = Alert(
          id: 'alert-1',
          companyId: 'comp-1',
          type: 'maintenance',
          title: 'Oil change',
          description: 'Do it now',
          severity: 'critical',
          isRead: true,
          createdAt: DateTime.utc(2024, 6, 15, 10, 30),
          relatedEntityId: 'v-42',
          relatedEntityType: 'vehicle',
        );
        final json = alert.toJson();
        expect(json['id'], 'alert-1');
        expect(json['companyId'], 'comp-1');
        expect(json['type'], 'maintenance');
        expect(json['title'], 'Oil change');
        expect(json['description'], 'Do it now');
        expect(json['severity'], 'critical');
        expect(json['isRead'], true);
        expect(json['createdAt'], '2024-06-15T10:30:00.000Z');
        expect(json['relatedEntityId'], 'v-42');
        expect(json['relatedEntityType'], 'vehicle');
      });

      test('round-trip fromJson → toJson produces same map', () {
        final original = {
          'id': 'rt-1',
          'companyId': 'comp-1',
          'type': 'delay',
          'title': 'Late',
          'description': 'Traffic jam',
          'severity': 'low',
          'isRead': false,
          'createdAt': '2024-07-20T14:00:00.000Z',
          'relatedEntityId': 'tr-99',
          'relatedEntityType': 'transport',
        };
        final alert = Alert.fromJson(original);
        final output = alert.toJson();
        expect(output['id'], 'rt-1');
        expect(output['companyId'], 'comp-1');
        expect(output['type'], 'delay');
        expect(output['title'], 'Late');
        expect(output['description'], 'Traffic jam');
        expect(output['severity'], 'low');
        expect(output['isRead'], false);
        expect(output['createdAt'], '2024-07-20T14:00:00.000Z');
        expect(output['relatedEntityId'], 'tr-99');
        expect(output['relatedEntityType'], 'transport');
      });

      test('includes null for nullable fields when null', () {
        final alert = Alert(
          id: 'a',
          companyId: 'c',
          type: 't',
          title: 'T',
          description: 'D',
          createdAt: DateTime.utc(2024, 1, 1),
        );
        final json = alert.toJson();
        expect(json['relatedEntityId'], isNull);
        expect(json['relatedEntityType'], isNull);
      });
    });

    // ---------------------------------------------------------------------------
    // copyWith
    // ---------------------------------------------------------------------------
    group('copyWith', () {
      test('returns same object when no arguments', () {
        final alert = Alert(
          id: 'a',
          companyId: 'c',
          type: 't',
          title: 'T',
          description: 'D',
          createdAt: DateTime.utc(2024, 1, 1),
        );
        final copy = alert.copyWith();
        expect(copy, alert);
      });

      test('overrides specified fields', () {
        final alert = Alert(
          id: 'a',
          companyId: 'c',
          type: 't',
          title: 'T',
          description: 'D',
          severity: 'medium',
          isRead: false,
          createdAt: DateTime.utc(2024, 1, 1),
        );
        final copy = alert.copyWith(
          id: 'b',
          title: 'New Title',
          severity: 'critical',
          isRead: true,
        );
        expect(copy.id, 'b');
        expect(copy.companyId, 'c');
        expect(copy.title, 'New Title');
        expect(copy.severity, 'critical');
        expect(copy.isRead, true);
        expect(copy.createdAt, DateTime.utc(2024, 1, 1));
      });

      test('copyWith preserves original when target field is not overridden', () {
        final alert = Alert(
          id: 'a',
          companyId: 'c',
          type: 't',
          title: 'T',
          description: 'D',
          createdAt: DateTime.utc(2024, 1, 1),
          relatedEntityId: 'old',
          relatedEntityType: 'old-type',
        );
        // copyWith uses `parameter ?? this.field`, so passing null does NOT override
        final copy = alert.copyWith(relatedEntityId: null);
        expect(copy.relatedEntityId, 'old');
        expect(copy.relatedEntityType, 'old-type');
      });

      test('copyWith overrides nullable fields when value is provided', () {
        final alert = Alert(
          id: 'a',
          companyId: 'c',
          type: 't',
          title: 'T',
          description: 'D',
          createdAt: DateTime.utc(2024, 1, 1),
        );
        final copy = alert.copyWith(relatedEntityId: 'new-id');
        expect(copy.relatedEntityId, 'new-id');
      });
    });

    // ---------------------------------------------------------------------------
    // Equality
    // ---------------------------------------------------------------------------
    group('equality', () {
      test('same values are equal', () {
        final a = Alert(
          id: 'a1',
          companyId: 'c1',
          type: 't',
          title: 'T',
          description: 'D',
          createdAt: DateTime.utc(2024, 1, 1),
        );
        final b = Alert(
          id: 'a1',
          companyId: 'c1',
          type: 't',
          title: 'T',
          description: 'D',
          createdAt: DateTime.utc(2024, 1, 1),
        );
        expect(a, b);
        expect(a.hashCode, b.hashCode);
      });

      test('different ids are not equal', () {
        final a = Alert(
          id: 'a1',
          companyId: 'c1',
          type: 't',
          title: 'T',
          description: 'D',
          createdAt: DateTime.utc(2024, 1, 1),
        );
        final b = Alert(
          id: 'a2',
          companyId: 'c1',
          type: 't',
          title: 'T',
          description: 'D',
          createdAt: DateTime.utc(2024, 1, 1),
        );
        expect(a, isNot(b));
      });

      test('different runtime types are not equal', () {
        final alert = Alert(
          id: 'a',
          companyId: 'c',
          type: 't',
          title: 'T',
          description: 'D',
          createdAt: DateTime.utc(2024, 1, 1),
        );
        expect(alert == Object(), isFalse);
      });
    });

    // ---------------------------------------------------------------------------
    // toString
    // ---------------------------------------------------------------------------
    group('toString', () {
      test('includes key fields', () {
        final alert = Alert(
          id: 'alert-1',
          companyId: 'c',
          type: 'maintenance',
          title: 'Oil change',
          description: 'D',
          createdAt: DateTime.utc(2024, 1, 1),
        );
        final str = alert.toString();
        expect(str, contains('alert-1'));
        expect(str, contains('maintenance'));
        expect(str, contains('Oil change'));
      });
    });
  });
}
