import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/shared/models/user.dart';

void main() {
  group('User', () {
    // ---------------------------------------------------------------------------
    // fromJson
    // ---------------------------------------------------------------------------
    group('fromJson', () {
      test('parses valid JSON correctly (camelCase)', () {
        final json = {
          'id': 'user-1',
          'email': 'john@example.com',
          'fullName': 'John Doe',
          'role': 'driver',
          'companyId': 'comp-1',
          'phone': '+40720123456',
          'avatarUrl': 'https://example.com/avatar.jpg',
        };
        final user = User.fromJson(json);
        expect(user.id, 'user-1');
        expect(user.email, 'john@example.com');
        expect(user.fullName, 'John Doe');
        expect(user.role, 'driver');
        expect(user.companyId, 'comp-1');
        expect(user.phone, '+40720123456');
        expect(user.avatarUrl, 'https://example.com/avatar.jpg');
      });

      test('parses snake_case fields (backend format)', () {
        final json = {
          'id': 'user-2',
          'email': 'jane@example.com',
          'display_name': 'Jane Smith',
          'role': 'dispatcher',
          'company_id': 'comp-2',
          'phone': '+40720999999',
          'avatarUrl': null,
        };
        final user = User.fromJson(json);
        expect(user.id, 'user-2');
        expect(user.email, 'jane@example.com');
        expect(user.fullName, 'Jane Smith');
        expect(user.role, 'dispatcher');
        expect(user.companyId, 'comp-2');
        expect(user.phone, '+40720999999');
        expect(user.avatarUrl, isNull);
      });

      test('prefers fullName over display_name when both present', () {
        final json = {
          'id': 'user-3',
          'email': 'test@test.com',
          'fullName': 'Full Name',
          'display_name': 'Display Name',
          'role': 'admin',
          'companyId': 'comp-3',
        };
        final user = User.fromJson(json);
        expect(user.fullName, 'Full Name');
      });

      test('parses id from int', () {
        final json = {
          'id': 42,
          'email': 'test@test.com',
          'fullName': 'Test',
          'role': 'fleet_manager',
          'companyId': 'comp-1',
        };
        final user = User.fromJson(json);
        expect(user.id, '42');
      });

      test('parses companyId from int', () {
        final json = {
          'id': 'u-1',
          'email': 'test@test.com',
          'fullName': 'Test',
          'role': 'driver',
          'companyId': 7,
        };
        final user = User.fromJson(json);
        expect(user.companyId, '7');
      });

      test('reads company_id (snake_case) as int', () {
        final json = {
          'id': 'u-1',
          'email': 'test@test.com',
          'fullName': 'Test',
          'role': 'driver',
          'company_id': 99,
        };
        final user = User.fromJson(json);
        expect(user.companyId, '99');
      });

      test('handles null values with defaults', () {
        final json = <String, dynamic>{
          'id': null,
          'email': null,
          'fullName': null,
          'role': null,
          'companyId': null,
          'phone': null,
          'avatarUrl': null,
        };
        final user = User.fromJson(json);
        expect(user.id, '');
        expect(user.email, '');
        expect(user.fullName, '');
        expect(user.role, '');
        expect(user.companyId, '');
        expect(user.phone, isNull);
        expect(user.avatarUrl, isNull);
      });

      test('handles missing keys with defaults', () {
        final user = User.fromJson(<String, dynamic>{});
        expect(user.id, '');
        expect(user.email, '');
        expect(user.fullName, '');
        expect(user.role, '');
        expect(user.companyId, '');
        expect(user.phone, isNull);
        expect(user.avatarUrl, isNull);
      });

      test('handles wrong types gracefully', () {
        // `as String?` on int/bool throws TypeError at runtime
        expect(
          () => User.fromJson({
            'email': 123,
            'fullName': true,
            'role': null,
          }),
          throwsA(isA<TypeError>()),
        );
        // Non-int/non-String id returns ''
        final user = User.fromJson({
          'id': ['notanid'],
          'email': 'a@b.com',
          'fullName': 'N',
          'role': 'driver',
          'companyId': 'c',
        });
        expect(user.id, '');
        // double companyId returns ''
        final user2 = User.fromJson({
          'id': 'u-1',
          'email': 'a@b.com',
          'fullName': 'N',
          'role': 'driver',
          'companyId': 45.6,
        });
        expect(user2.companyId, '');
      });

      test('handles empty strings', () {
        final json = {
          'id': '',
          'email': '',
          'fullName': '',
          'role': '',
          'companyId': '',
        };
        final user = User.fromJson(json);
        expect(user.id, '');
        expect(user.email, '');
        expect(user.fullName, '');
        expect(user.role, '');
        expect(user.companyId, '');
      });

      test('falls back to null for fullName when both fullName and display_name are missing', () {
        final json = {
          'id': 'u-1',
          'email': 'test@test.com',
          'role': 'driver',
          'companyId': 'c-1',
        };
        final user = User.fromJson(json);
        expect(user.fullName, '');
      });
    });

    // ---------------------------------------------------------------------------
    // toJson
    // ---------------------------------------------------------------------------
    group('toJson', () {
      test('produces correct map (camelCase)', () {
        final user = User(
          id: 'user-1',
          email: 'john@example.com',
          fullName: 'John Doe',
          role: 'driver',
          companyId: 'comp-1',
          phone: '+40720123456',
          avatarUrl: 'https://example.com/avatar.jpg',
        );
        final json = user.toJson();
        expect(json['id'], 'user-1');
        expect(json['email'], 'john@example.com');
        expect(json['fullName'], 'John Doe');
        expect(json['role'], 'driver');
        expect(json['companyId'], 'comp-1');
        expect(json['phone'], '+40720123456');
        expect(json['avatarUrl'], 'https://example.com/avatar.jpg');
      });

      test('round-trip fromJson → toJson produces same map', () {
        final original = {
          'id': 'rt-1',
          'email': 'rt@test.com',
          'fullName': 'Round Trip',
          'role': 'admin',
          'companyId': 'comp-99',
          'phone': null,
          'avatarUrl': null,
        };
        final user = User.fromJson(original);
        final output = user.toJson();
        expect(output['id'], 'rt-1');
        expect(output['email'], 'rt@test.com');
        expect(output['fullName'], 'Round Trip');
        expect(output['role'], 'admin');
        expect(output['companyId'], 'comp-99');
        expect(output['phone'], isNull);
        expect(output['avatarUrl'], isNull);
      });

      test('round-trip with int id', () {
        final original = {
          'id': 42,
          'email': 'test@test.com',
          'fullName': 'Test',
          'role': 'driver',
          'companyId': 'comp-1',
        };
        final user = User.fromJson(original);
        final output = user.toJson();
        // id was int, converted to String '42'
        expect(output['id'], '42');
      });
    });

    // ---------------------------------------------------------------------------
    // copyWith
    // ---------------------------------------------------------------------------
    group('copyWith', () {
      test('returns same object when no arguments', () {
        final user = User(
          id: 'u-1',
          email: 'e@e.com',
          fullName: 'N',
          role: 'driver',
          companyId: 'c-1',
        );
        expect(user.copyWith(), user);
      });

      test('overrides specified fields', () {
        final user = User(
          id: 'u-1',
          email: 'old@e.com',
          fullName: 'Old',
          role: 'driver',
          companyId: 'c-1',
        );
        final copy = user.copyWith(
          email: 'new@e.com',
          role: 'admin',
          phone: '+40720000000',
        );
        expect(copy.email, 'new@e.com');
        expect(copy.role, 'admin');
        expect(copy.phone, '+40720000000');
        expect(copy.id, 'u-1');
      });
    });

    // ---------------------------------------------------------------------------
    // Equality
    // ---------------------------------------------------------------------------
    group('equality', () {
      test('same values are equal', () {
        final a = User(
          id: 'u-1',
          email: 'e@e.com',
          fullName: 'N',
          role: 'driver',
          companyId: 'c-1',
        );
        final b = User(
          id: 'u-1',
          email: 'e@e.com',
          fullName: 'N',
          role: 'driver',
          companyId: 'c-1',
        );
        expect(a, b);
        expect(a.hashCode, b.hashCode);
      });

      test('different ids are not equal', () {
        final a = User(
          id: 'u-1',
          email: 'e@e.com',
          fullName: 'N',
          role: 'driver',
          companyId: 'c-1',
        );
        final b = User(
          id: 'u-2',
          email: 'e@e.com',
          fullName: 'N',
          role: 'driver',
          companyId: 'c-1',
        );
        expect(a, isNot(b));
      });
    });

    // ---------------------------------------------------------------------------
    // toString
    // ---------------------------------------------------------------------------
    group('toString', () {
      test('includes key fields', () {
        final user = User(
          id: 'user-1',
          email: 'john@example.com',
          fullName: 'John Doe',
          role: 'driver',
          companyId: 'comp-1',
        );
        final str = user.toString();
        expect(str, contains('user-1'));
        expect(str, contains('john@example.com'));
        expect(str, contains('John Doe'));
        expect(str, contains('driver'));
      });
    });
  });
}
