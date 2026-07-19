import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/auth/user_role.dart';

void main() {
  group('userRoleFromString', () {
    test('"driver" resolves to UserRole.driver', () {
      expect(userRoleFromString('driver'), UserRole.driver);
    });

    test('"sofer" resolves to UserRole.driver', () {
      expect(userRoleFromString('sofer'), UserRole.driver);
    });

    test('"dispatcher" resolves to UserRole.dispatcher', () {
      expect(userRoleFromString('dispatcher'), UserRole.dispatcher);
    });

    test('"fleet_manager" resolves to UserRole.dispatcher', () {
      expect(userRoleFromString('fleet_manager'), UserRole.dispatcher);
    });

    test('"manager" resolves to UserRole.manager', () {
      expect(userRoleFromString('manager'), UserRole.manager);
    });

    test('"admin" resolves to UserRole.admin', () {
      expect(userRoleFromString('admin'), UserRole.admin);
    });

    test('"owner" resolves to UserRole.admin', () {
      expect(userRoleFromString('owner'), UserRole.admin);
    });

    test('null/unrecognized role resolves to UserRole.driver (safe default)', () {
      expect(userRoleFromString(''), UserRole.driver);
      expect(userRoleFromString('unknown'), UserRole.driver);
      expect(userRoleFromString('super_admin'), UserRole.driver);
    });
  });

  group('UserRole.shellVariant', () {
    test('UserRole.driver resolves to AppShellVariant.driverShell', () {
      expect(UserRole.driver.shellVariant, AppShellVariant.driverShell);
    });

    test('UserRole.dispatcher resolves to AppShellVariant.managerShell', () {
      expect(UserRole.dispatcher.shellVariant, AppShellVariant.managerShell);
    });

    test('UserRole.manager resolves to AppShellVariant.managerShell', () {
      expect(UserRole.manager.shellVariant, AppShellVariant.managerShell);
    });

    test('UserRole.admin resolves to AppShellVariant.managerShell', () {
      expect(UserRole.admin.shellVariant, AppShellVariant.managerShell);
    });
  });

  group('error / null-safety', () {
    test('unrecognised string maps to UserRole.driver (safe default) then driverShell', () {
      final role = userRoleFromString('some_unknown_role');
      expect(role, UserRole.driver);
      expect(role.shellVariant, AppShellVariant.driverShell);
    });
  });
}
