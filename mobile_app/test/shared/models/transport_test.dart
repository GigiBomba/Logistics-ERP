import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/shared/models/transport.dart';

void main() {
  group('Transport', () {
    // ---------------------------------------------------------------------------
    // fromJson
    // ---------------------------------------------------------------------------
    group('fromJson', () {
      test('parses valid JSON correctly', () {
        final json = {
          'id': 'tr-42',
          'companyId': 'comp-1',
          'loadInfo': 'Electronics - 500kg',
          'origin': 'Bucharest',
          'destination': 'Cluj-Napoca',
          'waypoints': ['Sibiu', 'Brașov'],
          'status': 'in_transit',
          'assignedDriverId': 'driver-1',
          'assignedDriverName': 'John Doe',
          'vehicleId': 'v-7',
          'vehiclePlate': 'SB-01-ABC',
          'scheduledDate': '2024-06-15T08:00:00.000Z',
          'deliveredDate': null,
          'lastUpdated': '2024-06-15T14:30:00.000Z',
          'originLat': 44.4268,
          'originLng': 26.1025,
          'destLat': 46.7712,
          'destLng': 23.6236,
        };
        final t = Transport.fromJson(json);
        expect(t.id, 'tr-42');
        expect(t.companyId, 'comp-1');
        expect(t.loadInfo, 'Electronics - 500kg');
        expect(t.origin, 'Bucharest');
        expect(t.destination, 'Cluj-Napoca');
        expect(t.waypoints, ['Sibiu', 'Brașov']);
        expect(t.status, 'in_transit');
        expect(t.assignedDriverId, 'driver-1');
        expect(t.assignedDriverName, 'John Doe');
        expect(t.vehicleId, 'v-7');
        expect(t.vehiclePlate, 'SB-01-ABC');
        expect(t.scheduledDate, DateTime.utc(2024, 6, 15, 8, 0));
        expect(t.deliveredDate, isNull);
        expect(t.lastUpdated, DateTime.utc(2024, 6, 15, 14, 30));
        expect(t.originLat, 44.4268);
        expect(t.originLng, 26.1025);
        expect(t.destLat, 46.7712);
        expect(t.destLng, 23.6236);
      });

      test('handles null values with defaults', () {
        final json = <String, dynamic>{
          'id': null,
          'companyId': null,
          'loadInfo': null,
          'origin': null,
          'destination': null,
          'waypoints': null,
          'status': null,
          'assignedDriverId': null,
          'assignedDriverName': null,
          'vehicleId': null,
          'vehiclePlate': null,
          'scheduledDate': null,
          'deliveredDate': null,
          'lastUpdated': null,
          'originLat': null,
          'originLng': null,
          'destLat': null,
          'destLng': null,
        };
        final t = Transport.fromJson(json);
        expect(t.id, '');
        expect(t.companyId, '');
        expect(t.loadInfo, '');
        expect(t.origin, '');
        expect(t.destination, '');
        expect(t.waypoints, <String>[]);
        expect(t.status, '');
        expect(t.assignedDriverId, isNull);
        expect(t.assignedDriverName, isNull);
        expect(t.vehicleId, isNull);
        expect(t.vehiclePlate, isNull);
        expect(t.scheduledDate, isNull);
        expect(t.deliveredDate, isNull);
        expect(t.lastUpdated, isNull);
        expect(t.originLat, isNull);
        expect(t.originLng, isNull);
        expect(t.destLat, isNull);
        expect(t.destLng, isNull);
      });

      test('handles missing keys with defaults', () {
        final t = Transport.fromJson(<String, dynamic>{});
        expect(t.id, '');
        expect(t.waypoints, <String>[]);
        expect(t.assignedDriverId, isNull);
        expect(t.scheduledDate, isNull);
        expect(t.originLat, isNull);
      });

      test('handles wrong types gracefully', () {
        // `as String?` on int/bool throws TypeError at runtime
        expect(
          () => Transport.fromJson({
            'id': 123,
            'companyId': true,
            'loadInfo': null,
            'origin': 45.6,
            'destination': [],
            'waypoints': 'notalist',
            'status': 1,
          }),
          throwsA(isA<TypeError>()),
        );
      });

      test('parses waypoints from a list with non-string elements', () {
        final json = {
          'id': 'tr-1',
          'companyId': 'c',
          'loadInfo': 'L',
          'origin': 'O',
          'destination': 'D',
          'waypoints': [1, 2, 3],
          'status': 'planned',
        };
        final t = Transport.fromJson(json);
        expect(t.waypoints, ['1', '2', '3']);
      });

      test('parses empty waypoints list', () {
        final json = {
          'id': 'tr-1',
          'companyId': 'c',
          'loadInfo': 'L',
          'origin': 'O',
          'destination': 'D',
          'waypoints': <String>[],
          'status': 'planned',
        };
        final t = Transport.fromJson(json);
        expect(t.waypoints, <String>[]);
      });

      test('parses lat/lng from int', () {
        final json = {
          'id': 'tr-1',
          'companyId': 'c',
          'loadInfo': 'L',
          'origin': 'O',
          'destination': 'D',
          'status': 'planned',
          'originLat': 44,
          'originLng': 26,
        };
        final t = Transport.fromJson(json);
        expect(t.originLat, 44.0);
        expect(t.originLng, 26.0);
      });

      test('parses negative lat/lng', () {
        final json = {
          'id': 'tr-1',
          'companyId': 'c',
          'loadInfo': 'L',
          'origin': 'O',
          'destination': 'D',
          'status': 'planned',
          'originLat': -33.8568,
          'originLng': 151.2153,
        };
        final t = Transport.fromJson(json);
        expect(t.originLat, -33.8568);
        expect(t.originLng, 151.2153);
      });

      test('parses DateTime from int milliseconds', () {
        final ms = DateTime.utc(2024, 6, 15, 8, 0).millisecondsSinceEpoch;
        final json = {
          'id': 'tr-1',
          'companyId': 'c',
          'loadInfo': 'L',
          'origin': 'O',
          'destination': 'D',
          'status': 'planned',
          'scheduledDate': ms,
        };
        final t = Transport.fromJson(json);
        expect(
          t.scheduledDate,
          DateTime.fromMillisecondsSinceEpoch(ms),
        );
      });

      test('parses DateTime from int seconds', () {
        final seconds =
            DateTime.utc(2024, 6, 15).millisecondsSinceEpoch ~/ 1000;
        final json = {
          'id': 'tr-1',
          'companyId': 'c',
          'loadInfo': 'L',
          'origin': 'O',
          'destination': 'D',
          'status': 'planned',
          'scheduledDate': seconds,
        };
        final t = Transport.fromJson(json);
        expect(
          t.scheduledDate,
          DateTime.fromMillisecondsSinceEpoch(seconds * 1000),
        );
      });

      test('handles empty strings', () {
        final json = {
          'id': '',
          'companyId': '',
          'loadInfo': '',
          'origin': '',
          'destination': '',
          'waypoints': <String>[],
          'status': '',
        };
        final t = Transport.fromJson(json);
        expect(t.id, '');
        expect(t.origin, '');
        expect(t.destination, '');
        expect(t.status, '');
      });
    });

    // ---------------------------------------------------------------------------
    // toJson
    // ---------------------------------------------------------------------------
    group('toJson', () {
      test('produces correct map', () {
        final t = Transport(
          id: 'tr-42',
          companyId: 'comp-1',
          loadInfo: 'Electronics',
          origin: 'Bucharest',
          destination: 'Cluj',
          waypoints: ['Sibiu'],
          status: 'delivered',
          assignedDriverId: 'driver-1',
          assignedDriverName: 'John',
          vehicleId: 'v-7',
          vehiclePlate: 'SB-01-ABC',
          scheduledDate: DateTime.utc(2024, 6, 15, 8, 0),
          deliveredDate: DateTime.utc(2024, 6, 16, 12, 0),
          lastUpdated: DateTime.utc(2024, 6, 16, 14, 0),
          originLat: 44.4268,
          originLng: 26.1025,
          destLat: 46.7712,
          destLng: 23.6236,
        );
        final json = t.toJson();
        expect(json['id'], 'tr-42');
        expect(json['companyId'], 'comp-1');
        expect(json['loadInfo'], 'Electronics');
        expect(json['origin'], 'Bucharest');
        expect(json['destination'], 'Cluj');
        expect(json['waypoints'], ['Sibiu']);
        expect(json['status'], 'delivered');
        expect(json['assignedDriverId'], 'driver-1');
        expect(json['assignedDriverName'], 'John');
        expect(json['vehicleId'], 'v-7');
        expect(json['vehiclePlate'], 'SB-01-ABC');
        expect(json['scheduledDate'], '2024-06-15T08:00:00.000Z');
        expect(json['deliveredDate'], '2024-06-16T12:00:00.000Z');
        expect(json['lastUpdated'], '2024-06-16T14:00:00.000Z');
        expect(json['originLat'], 44.4268);
        expect(json['originLng'], 26.1025);
        expect(json['destLat'], 46.7712);
        expect(json['destLng'], 23.6236);
      });

      test('round-trip fromJson → toJson produces same map', () {
        final original = {
          'id': 'rt-1',
          'companyId': 'comp-1',
          'loadInfo': 'General cargo',
          'origin': 'Arad',
          'destination': 'Timișoara',
          'waypoints': <String>[],
          'status': 'planned',
          'assignedDriverId': null,
          'assignedDriverName': null,
          'vehicleId': null,
          'vehiclePlate': null,
          'scheduledDate': '2024-07-01T06:00:00.000Z',
          'deliveredDate': null,
          'lastUpdated': null,
          'originLat': null,
          'originLng': null,
          'destLat': null,
          'destLng': null,
        };
        final t = Transport.fromJson(original);
        final output = t.toJson();
        expect(output['id'], 'rt-1');
        expect(output['loadInfo'], 'General cargo');
        expect(output['waypoints'], <String>[]);
        expect(output['scheduledDate'], '2024-07-01T06:00:00.000Z');
        expect(output['deliveredDate'], isNull);
        expect(output['originLat'], isNull);
      });
    });

    // ---------------------------------------------------------------------------
    // copyWith
    // ---------------------------------------------------------------------------
    group('copyWith', () {
      test('returns same object when no arguments', () {
        final t = Transport(
          id: 'tr-1',
          companyId: 'c',
          loadInfo: 'L',
          origin: 'O',
          destination: 'D',
          status: 'planned',
        );
        expect(t.copyWith(), t);
      });

      test('overrides specified fields', () {
        final t = Transport(
          id: 'tr-1',
          companyId: 'c',
          loadInfo: 'L',
          origin: 'O',
          destination: 'D',
          status: 'planned',
        );
        final copy = t.copyWith(
          status: 'in_transit',
          assignedDriverName: 'John',
          vehiclePlate: 'SB-01-ABC',
        );
        expect(copy.status, 'in_transit');
        expect(copy.assignedDriverName, 'John');
        expect(copy.vehiclePlate, 'SB-01-ABC');
        expect(copy.id, 'tr-1');
      });
    });

    // ---------------------------------------------------------------------------
    // Equality
    // ---------------------------------------------------------------------------
    group('equality', () {
      test('same values are equal', () {
        final a = Transport(
          id: 'tr-1',
          companyId: 'c',
          loadInfo: 'L',
          origin: 'O',
          destination: 'D',
          status: 'planned',
        );
        final b = Transport(
          id: 'tr-1',
          companyId: 'c',
          loadInfo: 'L',
          origin: 'O',
          destination: 'D',
          status: 'planned',
        );
        expect(a, b);
        expect(a.hashCode, b.hashCode);
      });

      test('different ids are not equal', () {
        final a = Transport(
          id: 'tr-1',
          companyId: 'c',
          loadInfo: 'L',
          origin: 'O',
          destination: 'D',
          status: 'planned',
        );
        final b = Transport(
          id: 'tr-2',
          companyId: 'c',
          loadInfo: 'L',
          origin: 'O',
          destination: 'D',
          status: 'planned',
        );
        expect(a, isNot(b));
      });
    });

    // ---------------------------------------------------------------------------
    // toString
    // ---------------------------------------------------------------------------
    group('toString', () {
      test('includes key fields', () {
        final t = Transport(
          id: 'tr-42',
          companyId: 'c',
          loadInfo: 'Electronics',
          origin: 'Bucharest',
          destination: 'Cluj',
          status: 'in_transit',
        );
        final str = t.toString();
        expect(str, contains('tr-42'));
        expect(str, contains('Electronics'));
        expect(str, contains('Bucharest'));
        expect(str, contains('Cluj'));
        expect(str, contains('in_transit'));
      });
    });
  });
}
