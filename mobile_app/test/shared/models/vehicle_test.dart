import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/shared/models/vehicle.dart';
import 'package:operion_mobile/shared/models/vehicle_document.dart';

void main() {
  group('Vehicle', () {
    // ---------------------------------------------------------------------------
    // fromJson
    // ---------------------------------------------------------------------------
    group('fromJson', () {
      test('parses valid JSON correctly', () {
        final json = {
          'id': 'v-7',
          'companyId': 'comp-1',
          'plate': 'SB-01-ABC',
          'type': 'truck',
          'brand': 'Mercedes',
          'model': 'Actros',
          'status': 'active',
          'assignedDriverId': 'driver-1',
          'documents': [
            {
              'id': 'vd-1',
              'vehicleId': 'v-7',
              'documentType': 'ITP',
              'expiryDate': '2025-06-15T00:00:00.000',
              'isExpiringSoon': false,
            },
          ],
          'lastUpdated': '2024-06-15T14:30:00.000Z',
        };
        final v = Vehicle.fromJson(json);
        expect(v.id, 'v-7');
        expect(v.companyId, 'comp-1');
        expect(v.plate, 'SB-01-ABC');
        expect(v.type, 'truck');
        expect(v.brand, 'Mercedes');
        expect(v.model, 'Actros');
        expect(v.status, 'active');
        expect(v.assignedDriverId, 'driver-1');
        expect(v.documents, hasLength(1));
        expect(v.documents[0].id, 'vd-1');
        expect(v.documents[0].documentType, 'ITP');
        expect(v.lastUpdated, DateTime.utc(2024, 6, 15, 14, 30));
      });

      test('parses empty documents list', () {
        final json = {
          'id': 'v-1',
          'companyId': 'c',
          'plate': 'SB-01-ABC',
          'type': 'truck',
          'brand': 'M',
          'model': 'A',
          'status': 'active',
          'documents': <Map<String, dynamic>>[],
        };
        final v = Vehicle.fromJson(json);
        expect(v.documents, <VehicleDocument>[]);
      });

      test('handles null values with defaults', () {
        final json = <String, dynamic>{
          'id': null,
          'companyId': null,
          'plate': null,
          'type': null,
          'brand': null,
          'model': null,
          'status': null,
          'assignedDriverId': null,
          'documents': null,
          'lastUpdated': null,
        };
        final v = Vehicle.fromJson(json);
        expect(v.id, '');
        expect(v.companyId, '');
        expect(v.plate, '');
        expect(v.type, '');
        expect(v.brand, '');
        expect(v.model, '');
        expect(v.status, '');
        expect(v.assignedDriverId, isNull);
        expect(v.documents, <VehicleDocument>[]);
        expect(v.lastUpdated, isNull);
      });

      test('handles missing keys with defaults', () {
        final v = Vehicle.fromJson(<String, dynamic>{});
        expect(v.id, '');
        expect(v.plate, '');
        expect(v.type, '');
        expect(v.brand, '');
        expect(v.model, '');
        expect(v.status, '');
        expect(v.assignedDriverId, isNull);
        expect(v.documents, <VehicleDocument>[]);
        expect(v.lastUpdated, isNull);
      });

      test('handles wrong types gracefully', () {
        // `as String?` on int/bool throws TypeError at runtime
        expect(
          () => Vehicle.fromJson({
            'id': 123,
            'companyId': true,
            'plate': null,
            'type': 45.6,
            'brand': [],
            'model': null,
            'status': 1,
            'assignedDriverId': false,
            'documents': 'notalist',
          }),
          throwsA(isA<TypeError>()),
        );
      });

      test('throws on invalid document entries in documents list', () {
        // When documents list contains non-Map elements,
        // `as Map<String, dynamic>` cast throws TypeError
        expect(
          () => Vehicle.fromJson({
            'id': 'v-1',
            'companyId': 'c',
            'plate': 'SB-01-ABC',
            'type': 'truck',
            'brand': 'M',
            'model': 'A',
            'status': 'active',
            'documents': [
              {'id': 'vd-1', 'vehicleId': 'v-1', 'documentType': 'ITP'},
              'notamap',
              123,
            ],
          }),
          throwsA(isA<TypeError>()),
        );
      });

      test('parses DateTime from int milliseconds', () {
        final ms = DateTime.utc(2024, 6, 15).millisecondsSinceEpoch;
        final json = {
          'id': 'v-1',
          'companyId': 'c',
          'plate': 'SB-01-ABC',
          'type': 'truck',
          'brand': 'M',
          'model': 'A',
          'status': 'active',
          'lastUpdated': ms,
        };
        final v = Vehicle.fromJson(json);
        expect(
          v.lastUpdated,
          DateTime.fromMillisecondsSinceEpoch(ms),
        );
      });

      test('parses DateTime from int seconds', () {
        final seconds =
            DateTime.utc(2024, 6, 15).millisecondsSinceEpoch ~/ 1000;
        final json = {
          'id': 'v-1',
          'companyId': 'c',
          'plate': 'SB-01-ABC',
          'type': 'truck',
          'brand': 'M',
          'model': 'A',
          'status': 'active',
          'lastUpdated': seconds,
        };
        final v = Vehicle.fromJson(json);
        expect(
          v.lastUpdated,
          DateTime.fromMillisecondsSinceEpoch(seconds * 1000),
        );
      });

      test('handles empty strings', () {
        final json = {
          'id': '',
          'companyId': '',
          'plate': '',
          'type': '',
          'brand': '',
          'model': '',
          'status': '',
        };
        final v = Vehicle.fromJson(json);
        expect(v.id, '');
        expect(v.plate, '');
        expect(v.brand, '');
        expect(v.model, '');
      });
    });

    // ---------------------------------------------------------------------------
    // toJson
    // ---------------------------------------------------------------------------
    group('toJson', () {
      test('produces correct map', () {
        final v = Vehicle(
          id: 'v-7',
          companyId: 'comp-1',
          plate: 'SB-01-ABC',
          type: 'truck',
          brand: 'Mercedes',
          model: 'Actros',
          status: 'active',
          assignedDriverId: 'driver-1',
          documents: [
            VehicleDocument(
              id: 'vd-1',
              vehicleId: 'v-7',
              documentType: 'ITP',
              expiryDate: DateTime.utc(2025, 6, 15),
              isExpiringSoon: false,
            ),
          ],
          lastUpdated: DateTime.utc(2024, 6, 15, 14, 30),
        );
        final json = v.toJson();
        expect(json['id'], 'v-7');
        expect(json['companyId'], 'comp-1');
        expect(json['plate'], 'SB-01-ABC');
        expect(json['type'], 'truck');
        expect(json['brand'], 'Mercedes');
        expect(json['model'], 'Actros');
        expect(json['status'], 'active');
        expect(json['assignedDriverId'], 'driver-1');
        expect(json['documents'], hasLength(1));
        expect(json['documents'][0]['id'], 'vd-1');
        expect(json['documents'][0]['documentType'], 'ITP');
        expect(json['lastUpdated'], '2024-06-15T14:30:00.000Z');
      });

      test('round-trip fromJson → toJson produces same map', () {
        final original = {
          'id': 'rt-1',
          'companyId': 'comp-1',
          'plate': 'SB-99-ZZZ',
          'type': 'van',
          'brand': 'Ford',
          'model': 'Transit',
          'status': 'maintenance',
          'assignedDriverId': null,
          'documents': <Map<String, dynamic>>[],
          'lastUpdated': null,
        };
        final v = Vehicle.fromJson(original);
        final output = v.toJson();
        expect(output['id'], 'rt-1');
        expect(output['plate'], 'SB-99-ZZZ');
        expect(output['type'], 'van');
        expect(output['status'], 'maintenance');
        expect(output['documents'], <VehicleDocument>[]);
        expect(output['lastUpdated'], isNull);
      });

      test('omits lastUpdated when null', () {
        final v = Vehicle(
          id: 'v-1',
          companyId: 'c',
          plate: 'SB-01-ABC',
          type: 'truck',
          brand: 'M',
          model: 'A',
          status: 'active',
        );
        final json = v.toJson();
        expect(json['lastUpdated'], isNull);
      });
    });

    // ---------------------------------------------------------------------------
    // copyWith
    // ---------------------------------------------------------------------------
    group('copyWith', () {
      test('returns same object when no arguments', () {
        final v = Vehicle(
          id: 'v-1',
          companyId: 'c',
          plate: 'SB-01-ABC',
          type: 'truck',
          brand: 'M',
          model: 'A',
          status: 'active',
        );
        expect(v.copyWith(), v);
      });

      test('overrides specified fields', () {
        final v = Vehicle(
          id: 'v-1',
          companyId: 'c',
          plate: 'SB-01-ABC',
          type: 'truck',
          brand: 'Old',
          model: 'A',
          status: 'active',
        );
        final copy = v.copyWith(
          brand: 'New Brand',
          status: 'maintenance',
          assignedDriverId: 'driver-99',
        );
        expect(copy.brand, 'New Brand');
        expect(copy.status, 'maintenance');
        expect(copy.assignedDriverId, 'driver-99');
        expect(copy.id, 'v-1');
      });
    });

    // ---------------------------------------------------------------------------
    // Equality
    // ---------------------------------------------------------------------------
    group('equality', () {
      test('same values are equal', () {
        final a = Vehicle(
          id: 'v-1',
          companyId: 'c',
          plate: 'SB-01-ABC',
          type: 'truck',
          brand: 'M',
          model: 'A',
          status: 'active',
        );
        final b = Vehicle(
          id: 'v-1',
          companyId: 'c',
          plate: 'SB-01-ABC',
          type: 'truck',
          brand: 'M',
          model: 'A',
          status: 'active',
        );
        expect(a, b);
        expect(a.hashCode, b.hashCode);
      });

      test('different plates are not equal', () {
        final a = Vehicle(
          id: 'v-1',
          companyId: 'c',
          plate: 'SB-01-ABC',
          type: 'truck',
          brand: 'M',
          model: 'A',
          status: 'active',
        );
        final b = Vehicle(
          id: 'v-1',
          companyId: 'c',
          plate: 'SB-02-XYZ',
          type: 'truck',
          brand: 'M',
          model: 'A',
          status: 'active',
        );
        expect(a, isNot(b));
      });
    });

    // ---------------------------------------------------------------------------
    // toString
    // ---------------------------------------------------------------------------
    group('toString', () {
      test('includes key fields', () {
        final v = Vehicle(
          id: 'v-7',
          companyId: 'c',
          plate: 'SB-01-ABC',
          type: 'truck',
          brand: 'Mercedes',
          model: 'Actros',
          status: 'active',
        );
        final str = v.toString();
        expect(str, contains('v-7'));
        expect(str, contains('SB-01-ABC'));
        expect(str, contains('Mercedes'));
        expect(str, contains('Actros'));
        expect(str, contains('truck'));
        expect(str, contains('active'));
      });
    });
  });
}
