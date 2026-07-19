import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/core/sync/conflict_handler.dart';

void main() {
  group('ConflictHandler', () {
    // ======================================================================
    // resolveStatusConflict
    // ======================================================================

    group('resolveStatusConflict', () {
      test('returns Romanian string with transport ID and both statuses',
          () {
        final result = ConflictHandler.resolveStatusConflict(
          'TR-101',
          'delivered',
          'cancelled',
        );
        expect(result, contains('TR-101'));
        expect(result, contains('delivered'));
        expect(result, contains('cancelled'));
        expect(result, contains('Transportul'));
        expect(result, contains('statusul'));
      });

      test('includes attempted and current status in the message', () {
        final result = ConflictHandler.resolveStatusConflict(
          'TR-42',
          'loading',
          'in_transit',
        );
        expect(result, contains('loading'));
        expect(result, contains('in_transit'));
      });

      test('handles status values with special characters', () {
        final result = ConflictHandler.resolveStatusConflict(
          'TR-1',
          'en_route',
          'delayed (weather)',
        );
        expect(result, contains('en_route'));
        expect(result, contains('delayed (weather)'));
      });

      test('handles numeric IDs', () {
        final result = ConflictHandler.resolveStatusConflict(
          '42',
          'delivered',
          'cancelled',
        );
        expect(result, contains('42'));
      });

      test('handles very long transport IDs', () {
        final longId = 'TR-' + 'A' * 100;
        final result = ConflictHandler.resolveStatusConflict(
          longId,
          'delivered',
          'cancelled',
        );
        expect(result, contains(longId));
      });

      test('with empty strings still returns a message', () {
        final result = ConflictHandler.resolveStatusConflict('', '', '');
        expect(result, isNotEmpty);
        expect(result, contains('statusul'));
      });

      test('message mentions "reîmprospătate" (refreshed)', () {
        final result = ConflictHandler.resolveStatusConflict(
          'TR-001',
          'active',
          'archived',
        );
        expect(result, contains('reîmprospătate'));
      });

      test('message mentions "nu a fost posibilă" (not possible)', () {
        final result = ConflictHandler.resolveStatusConflict(
          'TR-99',
          'x',
          'y',
        );
        expect(result, contains('nu a fost posibilă'));
      });
    });

    // ======================================================================
    // resolveReassignConflict
    // ======================================================================

    group('resolveReassignConflict', () {
      test('returns Romanian string with transport ID', () {
        final result = ConflictHandler.resolveReassignConflict(
          'TR-202',
          'John',
        );
        expect(result, contains('TR-202'));
        expect(result, contains('Transportul'));
        expect(result, contains('realocat'));
      });

      test('does not include driver name in message (parameter unused)', () {
        // The method signature accepts attemptedDriver but does not
        // interpolate it in the output string.
        final result = ConflictHandler.resolveReassignConflict(
          'TR-50',
          'Ion Popescu',
        );
        expect(result, contains('TR-50'));
        expect(result, isNot(contains('Ion Popescu')));
      });

      test('handles Unicode driver names without error', () {
        final result = ConflictHandler.resolveReassignConflict(
          'TR-10',
          'Ștefan',
        );
        expect(result, contains('TR-10'));
        expect(result, isNotEmpty);
      });

      test('handles empty driver name', () {
        final result = ConflictHandler.resolveReassignConflict('TR-1', '');
        expect(result, isNotEmpty);
        expect(result, contains('TR-1'));
      });

      test('handles empty transport ID', () {
        final result = ConflictHandler.resolveReassignConflict('', 'Driver');
        expect(result, isNotEmpty);
      });

      test('with all empty strings still returns a message', () {
        final result = ConflictHandler.resolveReassignConflict('', '');
        expect(result, isNotEmpty);
      });

      test('message mentions "anulată" (cancelled)', () {
        final result = ConflictHandler.resolveReassignConflict(
          'TR-77',
          'Ana',
        );
        expect(result, contains('anulată'));
      });

      test('message mentions "altui șofer" (another driver)', () {
        final result = ConflictHandler.resolveReassignConflict(
          'TR-1',
          'Maria',
        );
        expect(result, contains('altui șofer'));
      });
    });

    // ======================================================================
    // resolveExpiredAction
    // ======================================================================

    group('resolveExpiredAction', () {
      test('returns Romanian string with action description', () {
        final result = ConflictHandler.resolveExpiredAction(
          'Schimbare status',
        );
        expect(result, contains('Schimbare status'));
        expect(result, contains('valabilă'));
      });

      test('handles action description with special characters', () {
        final result = ConflictHandler.resolveExpiredAction(
          'Atribuire șofer (prioritate: #1)',
        );
        expect(result, contains('Atribuire șofer (prioritate: #1)'));
      });

      test('handles long action descriptions', () {
        final longDesc = 'A' * 200;
        final result = ConflictHandler.resolveExpiredAction(longDesc);
        expect(result, contains(longDesc));
      });

      test('with empty action description still returns a message', () {
        final result = ConflictHandler.resolveExpiredAction('');
        expect(result, isNotEmpty);
      });

      test('message mentions "nu mai este valabilă" (no longer valid)', () {
        final result = ConflictHandler.resolveExpiredAction(
          'Ștergere document',
        );
        expect(result, contains('nu mai este valabilă'));
      });

      test('message mentions "Datele s-au modificat" (data changed)', () {
        final result = ConflictHandler.resolveExpiredAction('Editare');
        expect(result, contains('Datele s-au modificat'));
      });
    });

    // ======================================================================
    // Cross-method consistency
    // ======================================================================

    group('cross-method consistency', () {
      test('all methods return non-empty messages', () {
        expect(
          ConflictHandler.resolveStatusConflict('a', 'b', 'c'),
          isNotEmpty,
        );
        expect(
          ConflictHandler.resolveReassignConflict('a', 'b'),
          isNotEmpty,
        );
        expect(
          ConflictHandler.resolveExpiredAction('test'),
          isNotEmpty,
        );
      });

      test('all messages contain at least one Romanian word', () {
        expect(
          ConflictHandler.resolveStatusConflict('1', 'x', 'y'),
          anyOf(contains('Transportul'), contains('statusul')),
        );
        expect(
          ConflictHandler.resolveReassignConflict('1', 'x'),
          anyOf(contains('Transportul'), contains('realocat')),
        );
        expect(
          ConflictHandler.resolveExpiredAction('x'),
          anyOf(contains('valabilă'), contains('Datele')),
        );
      });
    });
  });
}
