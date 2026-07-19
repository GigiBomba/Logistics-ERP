import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/shared/models/vehicle_document.dart';

void main() {
  group('VehicleDocument', () {
    // ---------------------------------------------------------------------------
    // fromJson
    // ---------------------------------------------------------------------------
    group('fromJson', () {
      test('parses valid JSON correctly', () {
        final json = {
          'id': 'vd-1',
          'vehicleId': 'v-7',
          'documentType': 'ITP',
          'expiryDate': '2025-06-15T00:00:00.000Z',
          'isExpiringSoon': true,
        };
        final vd = VehicleDocument.fromJson(json);
        expect(vd.id, 'vd-1');
        expect(vd.vehicleId, 'v-7');
        expect(vd.documentType, 'ITP');
        expect(vd.expiryDate, DateTime.utc(2025, 6, 15));
        expect(vd.isExpiringSoon, true);
      });

      test('handles null values with defaults', () {
        final json = <String, dynamic>{
          'id': null,
          'vehicleId': null,
          'documentType': null,
          'expiryDate': null,
          'isExpiringSoon': null,
        };
        final vd = VehicleDocument.fromJson(json);
        expect(vd.id, '');
        expect(vd.vehicleId, '');
        expect(vd.documentType, '');
        expect(vd.expiryDate, isNull);
        expect(vd.isExpiringSoon, false);
      });

      test('handles missing keys with defaults', () {
        final vd = VehicleDocument.fromJson(<String, dynamic>{});
        expect(vd.id, '');
        expect(vd.vehicleId, '');
        expect(vd.documentType, '');
        expect(vd.expiryDate, isNull);
        expect(vd.isExpiringSoon, false);
      });

      test('handles wrong types gracefully', () {
        // `as String?` on int/bool throws TypeError at runtime
        expect(
          () => VehicleDocument.fromJson({
            'id': 123,
            'vehicleId': true,
            'documentType': null,
            'isExpiringSoon': 'notabool',
          }),
          throwsA(isA<TypeError>()),
        );
      });

      test('parses DateTime from int milliseconds', () {
        final ms = DateTime.utc(2025, 6, 15).millisecondsSinceEpoch;
        final json = {
          'id': 'vd-1',
          'vehicleId': 'v-1',
          'documentType': 'RCA',
          'expiryDate': ms,
        };
        final vd = VehicleDocument.fromJson(json);
        expect(
          vd.expiryDate,
          DateTime.fromMillisecondsSinceEpoch(ms),
        );
      });

      test('parses DateTime from int seconds', () {
        final seconds =
            DateTime.utc(2025, 6, 15).millisecondsSinceEpoch ~/ 1000;
        final json = {
          'id': 'vd-1',
          'vehicleId': 'v-1',
          'documentType': 'CASCO',
          'expiryDate': seconds,
        };
        final vd = VehicleDocument.fromJson(json);
        expect(
          vd.expiryDate,
          DateTime.fromMillisecondsSinceEpoch(seconds * 1000),
        );
      });

      test('handles empty strings', () {
        final json = {
          'id': '',
          'vehicleId': '',
          'documentType': '',
          'isExpiringSoon': false,
        };
        final vd = VehicleDocument.fromJson(json);
        expect(vd.id, '');
        expect(vd.vehicleId, '');
        expect(vd.documentType, '');
      });

      test('parses isExpiringSoon as true', () {
        final json = {
          'id': 'vd-1',
          'vehicleId': 'v-1',
          'documentType': 'ITP',
          'isExpiringSoon': true,
        };
        final vd = VehicleDocument.fromJson(json);
        expect(vd.isExpiringSoon, true);
      });
    });

    // ---------------------------------------------------------------------------
    // toJson
    // ---------------------------------------------------------------------------
    group('toJson', () {
      test('produces correct map', () {
        final vd = VehicleDocument(
          id: 'vd-1',
          vehicleId: 'v-7',
          documentType: 'ITP',
          expiryDate: DateTime.utc(2025, 6, 15),
          isExpiringSoon: true,
        );
        final json = vd.toJson();
        expect(json['id'], 'vd-1');
        expect(json['vehicleId'], 'v-7');
        expect(json['documentType'], 'ITP');
        expect(json['expiryDate'], '2025-06-15T00:00:00.000Z');
        expect(json['isExpiringSoon'], true);
      });

      test('round-trip fromJson → toJson produces same map', () {
        final original = {
          'id': 'rt-1',
          'vehicleId': 'v-99',
          'documentType': 'RCA',
          'expiryDate': null,
          'isExpiringSoon': false,
        };
        final vd = VehicleDocument.fromJson(original);
        final output = vd.toJson();
        expect(output['id'], 'rt-1');
        expect(output['vehicleId'], 'v-99');
        expect(output['documentType'], 'RCA');
        expect(output['expiryDate'], isNull);
        expect(output['isExpiringSoon'], false);
      });

      test('omits expiryDate when null', () {
        final vd = VehicleDocument(
          id: 'vd-1',
          vehicleId: 'v-1',
          documentType: 'ITP',
        );
        final json = vd.toJson();
        expect(json['expiryDate'], isNull);
      });
    });

    // ---------------------------------------------------------------------------
    // copyWith
    // ---------------------------------------------------------------------------
    group('copyWith', () {
      test('returns same object when no arguments', () {
        final vd = VehicleDocument(
          id: 'vd-1',
          vehicleId: 'v-1',
          documentType: 'ITP',
        );
        expect(vd.copyWith(), vd);
      });

      test('overrides specified fields', () {
        final vd = VehicleDocument(
          id: 'vd-1',
          vehicleId: 'v-1',
          documentType: 'ITP',
          isExpiringSoon: false,
        );
        final copy = vd.copyWith(
          documentType: 'RCA',
          isExpiringSoon: true,
        );
        expect(copy.documentType, 'RCA');
        expect(copy.isExpiringSoon, true);
        expect(copy.id, 'vd-1');
      });
    });

    // ---------------------------------------------------------------------------
    // Equality
    // ---------------------------------------------------------------------------
    group('equality', () {
      test('same values are equal', () {
        final a = VehicleDocument(
          id: 'vd-1',
          vehicleId: 'v-1',
          documentType: 'ITP',
        );
        final b = VehicleDocument(
          id: 'vd-1',
          vehicleId: 'v-1',
          documentType: 'ITP',
        );
        expect(a, b);
        expect(a.hashCode, b.hashCode);
      });

      test('different ids are not equal', () {
        final a = VehicleDocument(
          id: 'vd-1',
          vehicleId: 'v-1',
          documentType: 'ITP',
        );
        final b = VehicleDocument(
          id: 'vd-2',
          vehicleId: 'v-1',
          documentType: 'ITP',
        );
        expect(a, isNot(b));
      });
    });

    // ---------------------------------------------------------------------------
    // toString
    // ---------------------------------------------------------------------------
    group('toString', () {
      test('includes key fields', () {
        final vd = VehicleDocument(
          id: 'vd-1',
          vehicleId: 'v-7',
          documentType: 'ITP',
        );
        final str = vd.toString();
        expect(str, contains('vd-1'));
        expect(str, contains('v-7'));
        expect(str, contains('ITP'));
      });
    });
  });
}
