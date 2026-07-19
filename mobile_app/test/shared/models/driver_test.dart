import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/shared/models/driver.dart';

void main() {
  group('Driver', () {
    // ---------------------------------------------------------------------------
    // fromJson
    // ---------------------------------------------------------------------------
    group('fromJson', () {
      test('parses valid JSON correctly', () {
        final json = {
          'id': 'driver-1',
          'companyId': 'comp-1',
          'userId': 'user-1',
          'fullName': 'John Doe',
          'phone': '+40720123456',
          'status': 'driving',
          'currentTransportId': 'tr-42',
          'currentVehicleId': 'v-7',
          'lastActivity': '2024-06-15T14:30:00.000Z',
        };
        final driver = Driver.fromJson(json);
        expect(driver.id, 'driver-1');
        expect(driver.companyId, 'comp-1');
        expect(driver.userId, 'user-1');
        expect(driver.fullName, 'John Doe');
        expect(driver.phone, '+40720123456');
        expect(driver.status, 'driving');
        expect(driver.currentTransportId, 'tr-42');
        expect(driver.currentVehicleId, 'v-7');
        expect(driver.lastActivity, DateTime.utc(2024, 6, 15, 14, 30));
      });

      test('handles null values with defaults', () {
        final json = <String, dynamic>{
          'id': null,
          'companyId': null,
          'userId': null,
          'fullName': null,
          'phone': null,
          'status': null,
          'currentTransportId': null,
          'currentVehicleId': null,
          'lastActivity': null,
        };
        final driver = Driver.fromJson(json);
        expect(driver.id, '');
        expect(driver.companyId, '');
        expect(driver.userId, '');
        expect(driver.fullName, '');
        expect(driver.phone, '');
        expect(driver.status, 'available');
        expect(driver.currentTransportId, isNull);
        expect(driver.currentVehicleId, isNull);
        expect(driver.lastActivity, isNull);
      });

      test('handles missing keys with defaults', () {
        final driver = Driver.fromJson(<String, dynamic>{});
        expect(driver.id, '');
        expect(driver.status, 'available');
        expect(driver.currentTransportId, isNull);
        expect(driver.lastActivity, isNull);
      });

      test('handles wrong types gracefully', () {
        // `as String?` on int/bool throws TypeError at runtime
        expect(
          () => Driver.fromJson({
            'id': 123,
            'companyId': true,
            'userId': null,
            'fullName': 45.6,
            'phone': [],
            'status': 1,
          }),
          throwsA(isA<TypeError>()),
        );
      });

      test('parses DateTime from int milliseconds', () {
        final ms = DateTime.utc(2024, 1, 15).millisecondsSinceEpoch;
        final json = {
          'id': 'd',
          'companyId': 'c',
          'userId': 'u',
          'fullName': 'N',
          'phone': 'P',
          'lastActivity': ms,
        };
        final driver = Driver.fromJson(json);
        expect(
          driver.lastActivity,
          DateTime.fromMillisecondsSinceEpoch(ms),
        );
      });

      test('parses DateTime from int seconds', () {
        final seconds = DateTime.utc(2024, 6, 15).millisecondsSinceEpoch ~/ 1000;
        final json = {
          'id': 'd',
          'companyId': 'c',
          'userId': 'u',
          'fullName': 'N',
          'phone': 'P',
          'lastActivity': seconds,
        };
        final driver = Driver.fromJson(json);
        expect(
          driver.lastActivity,
          DateTime.fromMillisecondsSinceEpoch(seconds * 1000),
        );
      });

      test('handles empty strings in fields', () {
        final json = {
          'id': '',
          'companyId': '',
          'userId': '',
          'fullName': '',
          'phone': '',
          'status': '',
        };
        final driver = Driver.fromJson(json);
        expect(driver.id, '');
        expect(driver.fullName, '');
        expect(driver.status, '');
        expect(driver.phone, '');
      });
    });

    // ---------------------------------------------------------------------------
    // toJson
    // ---------------------------------------------------------------------------
    group('toJson', () {
      test('produces correct map', () {
        final driver = Driver(
          id: 'driver-1',
          companyId: 'comp-1',
          userId: 'user-1',
          fullName: 'John Doe',
          phone: '+40720123456',
          status: 'available',
          currentTransportId: 'tr-42',
          currentVehicleId: 'v-7',
          lastActivity: DateTime.utc(2024, 6, 15, 14, 30),
        );
        final json = driver.toJson();
        expect(json['id'], 'driver-1');
        expect(json['companyId'], 'comp-1');
        expect(json['userId'], 'user-1');
        expect(json['fullName'], 'John Doe');
        expect(json['phone'], '+40720123456');
        expect(json['status'], 'available');
        expect(json['currentTransportId'], 'tr-42');
        expect(json['currentVehicleId'], 'v-7');
        expect(json['lastActivity'], '2024-06-15T14:30:00.000Z');
      });

      test('round-trip fromJson → toJson produces same map', () {
        final original = {
          'id': 'rt-1',
          'companyId': 'comp-1',
          'userId': 'u-1',
          'fullName': 'Jane',
          'phone': '+40720999999',
          'status': 'off',
          'currentTransportId': null,
          'currentVehicleId': null,
          'lastActivity': null,
        };
        final driver = Driver.fromJson(original);
        final output = driver.toJson();
        expect(output['id'], 'rt-1');
        expect(output['companyId'], 'comp-1');
        expect(output['userId'], 'u-1');
        expect(output['fullName'], 'Jane');
        expect(output['phone'], '+40720999999');
        expect(output['status'], 'off');
        expect(output['currentTransportId'], isNull);
        expect(output['currentVehicleId'], isNull);
        expect(output['lastActivity'], isNull);
      });

      test('omits lastActivity when null', () {
        final driver = Driver(
          id: 'd',
          companyId: 'c',
          userId: 'u',
          fullName: 'N',
          phone: 'P',
        );
        final json = driver.toJson();
        expect(json['lastActivity'], isNull);
      });
    });

    // ---------------------------------------------------------------------------
    // copyWith
    // ---------------------------------------------------------------------------
    group('copyWith', () {
      test('returns same object when no arguments', () {
        final driver = Driver(
          id: 'd',
          companyId: 'c',
          userId: 'u',
          fullName: 'N',
          phone: 'P',
        );
        expect(driver.copyWith(), driver);
      });

      test('overrides specified fields', () {
        final driver = Driver(
          id: 'd',
          companyId: 'c',
          userId: 'u',
          fullName: 'Old Name',
          phone: 'P',
          status: 'available',
        );
        final copy = driver.copyWith(
          fullName: 'New Name',
          status: 'driving',
          currentTransportId: 'tr-99',
        );
        expect(copy.fullName, 'New Name');
        expect(copy.status, 'driving');
        expect(copy.currentTransportId, 'tr-99');
        expect(copy.id, 'd');
      });
    });

    // ---------------------------------------------------------------------------
    // Equality
    // ---------------------------------------------------------------------------
    group('equality', () {
      test('same values are equal', () {
        final a = Driver(
          id: 'd1',
          companyId: 'c1',
          userId: 'u1',
          fullName: 'N',
          phone: 'P',
        );
        final b = Driver(
          id: 'd1',
          companyId: 'c1',
          userId: 'u1',
          fullName: 'N',
          phone: 'P',
        );
        expect(a, b);
        expect(a.hashCode, b.hashCode);
      });

      test('different ids are not equal', () {
        final a = Driver(
          id: 'd1',
          companyId: 'c1',
          userId: 'u1',
          fullName: 'N',
          phone: 'P',
        );
        final b = Driver(
          id: 'd2',
          companyId: 'c1',
          userId: 'u1',
          fullName: 'N',
          phone: 'P',
        );
        expect(a, isNot(b));
      });
    });

    // ---------------------------------------------------------------------------
    // toString
    // ---------------------------------------------------------------------------
    group('toString', () {
      test('includes key fields', () {
        final driver = Driver(
          id: 'driver-1',
          companyId: 'c',
          userId: 'u',
          fullName: 'John Doe',
          phone: '+40720123456',
        );
        final str = driver.toString();
        expect(str, contains('driver-1'));
        expect(str, contains('John Doe'));
        expect(str, contains('+40720123456'));
      });
    });
  });
}
