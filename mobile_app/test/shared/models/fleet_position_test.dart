import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/shared/models/fleet_position.dart';

void main() {
  group('FleetPosition', () {
    // ---------------------------------------------------------------------------
    // fromJson – note: API uses snake_case keys
    // ---------------------------------------------------------------------------
    group('fromJson', () {
      test('parses valid JSON correctly', () {
        final json = {
          'vehicle_id': 'v-42',
          'plate': 'SB-01-ABC',
          'driver_name': 'John Doe',
          'lat': 45.9432,
          'lng': 24.9668,
          'status': 'moving',
          'last_update': '2024-06-15T10:30:00.000Z',
        };
        final pos = FleetPosition.fromJson(json);
        expect(pos.vehicleId, 'v-42');
        expect(pos.plate, 'SB-01-ABC');
        expect(pos.driverName, 'John Doe');
        expect(pos.latitude, 45.9432);
        expect(pos.longitude, 24.9668);
        expect(pos.status, 'moving');
        expect(pos.lastUpdate, DateTime.utc(2024, 6, 15, 10, 30));
      });

      test('handles null values with defaults', () {
        final json = <String, dynamic>{
          'vehicle_id': null,
          'plate': null,
          'driver_name': null,
          'lat': null,
          'lng': null,
          'status': null,
          'last_update': null,
        };
        final pos = FleetPosition.fromJson(json);
        expect(pos.vehicleId, '');
        expect(pos.plate, '');
        expect(pos.driverName, '');
        expect(pos.latitude, 0.0);
        expect(pos.longitude, 0.0);
        expect(pos.status, '');
        expect(pos.lastUpdate, isA<DateTime>());
      });

      test('handles missing keys with defaults', () {
        final pos = FleetPosition.fromJson(<String, dynamic>{});
        expect(pos.vehicleId, '');
        expect(pos.plate, '');
        expect(pos.driverName, '');
        expect(pos.latitude, 0.0);
        expect(pos.longitude, 0.0);
        expect(pos.status, '');
        expect(pos.lastUpdate, isA<DateTime>());
      });

      test('handles wrong types gracefully', () {
        // `as String?` on int/bool throws TypeError at runtime
        expect(
          () => FleetPosition.fromJson({
            'vehicle_id': 123,
            'plate': true,
            'driver_name': null,
            'lat': 'notanumber',
            'lng': 'notanumber',
            'status': 45.6,
            'last_update': [],
          }),
          throwsA(isA<TypeError>()),
        );
      });

      test('parses lat/lng from int', () {
        final json = {
          'vehicle_id': 'v-1',
          'plate': 'SB-01-ABC',
          'driver_name': 'John',
          'lat': 46,
          'lng': 25,
          'status': 'stopped',
          'last_update': '2024-01-01T00:00:00.000Z',
        };
        final pos = FleetPosition.fromJson(json);
        expect(pos.latitude, 46.0);
        expect(pos.longitude, 25.0);
      });

      test('parses negative lat/lng', () {
        final json = {
          'vehicle_id': 'v-1',
          'plate': 'SB-01-ABC',
          'driver_name': 'John',
          'lat': -33.8568,
          'lng': 151.2153,
          'status': 'moving',
          'last_update': '2024-01-01T00:00:00.000Z',
        };
        final pos = FleetPosition.fromJson(json);
        expect(pos.latitude, -33.8568);
        expect(pos.longitude, 151.2153);
      });

      test('parses very large lat/lng', () {
        final json = {
          'vehicle_id': 'v-1',
          'plate': 'SB-01-ABC',
          'driver_name': 'John',
          'lat': 90.0,
          'lng': 180.0,
          'status': 'moving',
          'last_update': '2024-01-01T00:00:00.000Z',
        };
        final pos = FleetPosition.fromJson(json);
        expect(pos.latitude, 90.0);
        expect(pos.longitude, 180.0);
      });

      test('parses DateTime from int milliseconds', () {
        final ms = DateTime.utc(2024, 6, 15).millisecondsSinceEpoch;
        final json = {
          'vehicle_id': 'v-1',
          'plate': 'SB-01-ABC',
          'driver_name': 'John',
          'lat': 0.0,
          'lng': 0.0,
          'status': 'stopped',
          'last_update': ms,
        };
        final pos = FleetPosition.fromJson(json);
        expect(
          pos.lastUpdate,
          DateTime.fromMillisecondsSinceEpoch(ms),
        );
      });

      test('parses DateTime from int seconds', () {
        final seconds = DateTime.utc(2024, 6, 15).millisecondsSinceEpoch ~/ 1000;
        final json = {
          'vehicle_id': 'v-1',
          'plate': 'SB-01-ABC',
          'driver_name': 'John',
          'lat': 0.0,
          'lng': 0.0,
          'status': 'stopped',
          'last_update': seconds,
        };
        final pos = FleetPosition.fromJson(json);
        expect(
          pos.lastUpdate,
          DateTime.fromMillisecondsSinceEpoch(seconds * 1000),
        );
      });

      test('handles empty strings', () {
        final json = {
          'vehicle_id': '',
          'plate': '',
          'driver_name': '',
          'lat': 0.0,
          'lng': 0.0,
          'status': '',
          'last_update': '2024-01-01T00:00:00.000Z',
        };
        final pos = FleetPosition.fromJson(json);
        expect(pos.vehicleId, '');
        expect(pos.plate, '');
        expect(pos.driverName, '');
        expect(pos.status, '');
      });
    });

    // ---------------------------------------------------------------------------
    // toJson
    // ---------------------------------------------------------------------------
    group('toJson', () {
      test('produces correct map with snake_case keys', () {
        final pos = FleetPosition(
          vehicleId: 'v-42',
          plate: 'SB-01-ABC',
          driverName: 'John Doe',
          latitude: 45.9432,
          longitude: 24.9668,
          status: 'moving',
          lastUpdate: DateTime.utc(2024, 6, 15, 10, 30),
        );
        final json = pos.toJson();
        expect(json['vehicle_id'], 'v-42');
        expect(json['plate'], 'SB-01-ABC');
        expect(json['driver_name'], 'John Doe');
        expect(json['lat'], 45.9432);
        expect(json['lng'], 24.9668);
        expect(json['status'], 'moving');
        expect(json['last_update'], '2024-06-15T10:30:00.000Z');
      });

      test('round-trip fromJson → toJson produces same map', () {
        final original = {
          'vehicle_id': 'rt-1',
          'plate': 'SB-99-ZZZ',
          'driver_name': 'Jane',
          'lat': 44.5,
          'lng': 26.1,
          'status': 'stopped',
          'last_update': '2024-07-20T08:00:00.000Z',
        };
        final pos = FleetPosition.fromJson(original);
        final output = pos.toJson();
        expect(output['vehicle_id'], 'rt-1');
        expect(output['plate'], 'SB-99-ZZZ');
        expect(output['driver_name'], 'Jane');
        expect(output['lat'], 44.5);
        expect(output['lng'], 26.1);
        expect(output['status'], 'stopped');
        expect(output['last_update'], '2024-07-20T08:00:00.000Z');
      });
    });

    // ---------------------------------------------------------------------------
    // Equality
    // ---------------------------------------------------------------------------
    group('equality', () {
      test('same values are equal', () {
        final a = FleetPosition(
          vehicleId: 'v1',
          plate: 'SB-01-ABC',
          driverName: 'John',
          latitude: 45.0,
          longitude: 25.0,
          status: 'moving',
          lastUpdate: DateTime.utc(2024, 1, 1),
        );
        final b = FleetPosition(
          vehicleId: 'v1',
          plate: 'SB-01-ABC',
          driverName: 'John',
          latitude: 45.0,
          longitude: 25.0,
          status: 'moving',
          lastUpdate: DateTime.utc(2024, 1, 1),
        );
        expect(a, b);
        expect(a.hashCode, b.hashCode);
      });

      test('different vehicle ids are not equal', () {
        final a = FleetPosition(
          vehicleId: 'v1',
          plate: 'SB-01-ABC',
          driverName: 'John',
          latitude: 45.0,
          longitude: 25.0,
          status: 'moving',
          lastUpdate: DateTime.utc(2024, 1, 1),
        );
        final b = FleetPosition(
          vehicleId: 'v2',
          plate: 'SB-01-ABC',
          driverName: 'John',
          latitude: 45.0,
          longitude: 25.0,
          status: 'moving',
          lastUpdate: DateTime.utc(2024, 1, 1),
        );
        expect(a, isNot(b));
      });
    });

    // ---------------------------------------------------------------------------
    // toString
    // ---------------------------------------------------------------------------
    group('toString', () {
      test('includes key fields', () {
        final pos = FleetPosition(
          vehicleId: 'v-42',
          plate: 'SB-01-ABC',
          driverName: 'John Doe',
          latitude: 45.9432,
          longitude: 24.9668,
          status: 'moving',
          lastUpdate: DateTime.utc(2024, 1, 1),
        );
        final str = pos.toString();
        expect(str, contains('v-42'));
        expect(str, contains('SB-01-ABC'));
        expect(str, contains('John Doe'));
        expect(str, contains('45.9432'));
        expect(str, contains('24.9668'));
        expect(str, contains('moving'));
      });
    });
  });
}
