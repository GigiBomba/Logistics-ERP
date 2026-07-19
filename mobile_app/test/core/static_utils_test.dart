import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/auth/user_role.dart';
import 'package:operion_mobile/core/sync/conflict_handler.dart';
import 'package:operion_mobile/core/notifications/notification_router.dart';
import 'package:operion_mobile/shared/widgets/transport_status_actions.dart';

void main() {
  // ==========================================================================
  // userRoleFromString
  // ==========================================================================
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
    test('"admin" resolves to UserRole.admin', () {
      expect(userRoleFromString('admin'), UserRole.admin);
    });
    test('"owner" resolves to UserRole.admin', () {
      expect(userRoleFromString('owner'), UserRole.admin);
    });
    test('unknown role defaults to UserRole.driver (safe default)', () {
      expect(userRoleFromString('unknown_role'), UserRole.driver);
      expect(userRoleFromString(''), UserRole.driver);
    });
  });

  group('AppShellRouting', () {
    test('driver → driverShell', () {
      expect(UserRole.driver.shellVariant, AppShellVariant.driverShell);
    });
    test('dispatcher → managerShell', () {
      expect(UserRole.dispatcher.shellVariant, AppShellVariant.managerShell);
    });
    test('manager → managerShell', () {
      expect(UserRole.manager.shellVariant, AppShellVariant.managerShell);
    });
    test('admin → managerShell (not a third shell)', () {
      expect(UserRole.admin.shellVariant, AppShellVariant.managerShell);
    });
  });

  // ==========================================================================
  // ConflictHandler
  // ==========================================================================
  group('ConflictHandler', () {
    test(
        'resolveStatusConflict returns Romanian string with transport ID and both statuses',
        () {
      final result =
          ConflictHandler.resolveStatusConflict('TR-101', 'delivered', 'cancelled');
      expect(result, contains('TR-101'));
      expect(result, contains('delivered'));
      expect(result, contains('cancelled'));
      expect(result, contains('Transportul'));
    });

    test('resolveStatusConflict with empty strings still returns a message', () {
      final result =
          ConflictHandler.resolveStatusConflict('', '', '');
      expect(result, isNotEmpty);
    });

    test(
        'resolveReassignConflict returns Romanian string with transport ID',
        () {
      final result =
          ConflictHandler.resolveReassignConflict('TR-202', 'John');
      expect(result, contains('TR-202'));
      expect(result, contains('Transportul'));
      expect(result, contains('realocat'));
    });

    test('resolveReassignConflict with empty transportId still returns message',
        () {
      final result = ConflictHandler.resolveReassignConflict('', '');
      expect(result, isNotEmpty);
    });

    test(
        'resolveExpiredAction returns Romanian string with action description',
        () {
      final result = ConflictHandler.resolveExpiredAction('Schimbare status');
      expect(result, contains('Schimbare status'));
      expect(result, contains('valabilă'));
    });

    test('resolveExpiredAction with empty action description still returns message',
        () {
      final result = ConflictHandler.resolveExpiredAction('');
      expect(result, isNotEmpty);
    });
  });

  // ==========================================================================
  // NotificationRouter
  // ==========================================================================
  group('NotificationRouter', () {
    group('resolveRoute', () {
      test('new_assignment → transportDetail', () {
        expect(
          NotificationRouter.resolveRoute({'type': 'new_assignment'}),
          NotificationRoute.transportDetail,
        );
      });

      test('status_change → transportDetail', () {
        expect(
          NotificationRouter.resolveRoute({'type': 'status_change'}),
          NotificationRoute.transportDetail,
        );
      });

      test('new_message → messageThread', () {
        expect(
          NotificationRouter.resolveRoute({'type': 'new_message'}),
          NotificationRoute.messageThread,
        );
      });

      test('alert → alertDetail', () {
        expect(
          NotificationRouter.resolveRoute({'type': 'alert'}),
          NotificationRoute.alertDetail,
        );
      });

      test('approval → alertDetail', () {
        expect(
          NotificationRouter.resolveRoute({'type': 'approval'}),
          NotificationRoute.alertDetail,
        );
      });

      test('driver_home → driverHome', () {
        expect(
          NotificationRouter.resolveRoute({'type': 'driver_home'}),
          NotificationRoute.driverHome,
        );
      });

      test('dispatcher_home → dispatcherHome', () {
        expect(
          NotificationRouter.resolveRoute({'type': 'dispatcher_home'}),
          NotificationRoute.dispatcherHome,
        );
      });

      test('unknown type returns null', () {
        expect(
          NotificationRouter.resolveRoute({'type': 'unknown_type'}),
          isNull,
        );
      });

      test('null type returns null', () {
        expect(
          NotificationRouter.resolveRoute({'type': null}),
          isNull,
        );
        expect(
          NotificationRouter.resolveRoute(<String, dynamic>{}),
          isNull,
        );
      });
    });

    group('resolveParams', () {
      test('extracts transport_id', () {
        final params = NotificationRouter.resolveParams({
          'transport_id': 'TR-42',
        });
        expect(params, isNotNull);
        expect(params!['transportId'], 'TR-42');
      });

      test('extracts thread_id', () {
        final params = NotificationRouter.resolveParams({
          'thread_id': 'thread-007',
        });
        expect(params, isNotNull);
        expect(params!['threadId'], 'thread-007');
      });

      test('returns null for empty data', () {
        final params = NotificationRouter.resolveParams({});
        expect(params, isNull);
      });
    });
  });

  // ==========================================================================
  // TransportStatusActions
  // ==========================================================================
  group('TransportStatusActions', () {
    group('getNextActions', () {
      test("'planned' returns loading as primary action", () {
        final actions = TransportStatusActions.getNextActions('planned');
        expect(actions, hasLength(1));
        expect(actions[0].status, 'loading');
        expect(actions[0].label, 'Start Loading');
        expect(actions[0].isPrimary, isTrue);
      });

      test("'loading' returns in_transit as primary action", () {
        final actions = TransportStatusActions.getNextActions('loading');
        expect(actions, hasLength(1));
        expect(actions[0].status, 'in_transit');
        expect(actions[0].label, 'Depart');
        expect(actions[0].isPrimary, isTrue);
      });

      test("'in_transit' returns delivered (primary) + overdue (secondary)", () {
        final actions = TransportStatusActions.getNextActions('in_transit');
        expect(actions, hasLength(2));
        expect(actions[0].status, 'delivered');
        expect(actions[0].isPrimary, isTrue);
        expect(actions[1].status, 'overdue');
        expect(actions[1].isPrimary, isFalse);
      });

      test("'delivered' returns empty list", () {
        final actions = TransportStatusActions.getNextActions('delivered');
        expect(actions, isEmpty);
      });

      test("'cancelled' returns empty list", () {
        final actions = TransportStatusActions.getNextActions('cancelled');
        expect(actions, isEmpty);
      });

      test("'' (empty string) returns empty list", () {
        final actions = TransportStatusActions.getNextActions('');
        expect(actions, isEmpty);
      });
    });

    group('isTerminal', () {
      test('delivered is terminal', () {
        expect(TransportStatusActions.isTerminal('delivered'), isTrue);
      });
      test('cancelled is terminal', () {
        expect(TransportStatusActions.isTerminal('cancelled'), isTrue);
      });
      test('planned is not terminal', () {
        expect(TransportStatusActions.isTerminal('planned'), isFalse);
      });
    });
  });
}
