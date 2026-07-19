import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/shared/models/message.dart';

void main() {
  group('Message', () {
    // ---------------------------------------------------------------------------
    // fromJson
    // ---------------------------------------------------------------------------
    group('fromJson', () {
      test('parses valid JSON correctly', () {
        final json = {
          'id': 'msg-1',
          'senderId': 'user-1',
          'senderName': 'John Doe',
          'receiverId': 'user-2',
          'text': 'Hello, please confirm the delivery time.',
          'timestamp': '2024-06-15T10:30:00.000Z',
          'isRead': true,
          'transportId': 'tr-42',
          'hasFailed': false,
        };
        final msg = Message.fromJson(json);
        expect(msg.id, 'msg-1');
        expect(msg.senderId, 'user-1');
        expect(msg.senderName, 'John Doe');
        expect(msg.receiverId, 'user-2');
        expect(msg.text, 'Hello, please confirm the delivery time.');
        expect(msg.timestamp, DateTime.utc(2024, 6, 15, 10, 30));
        expect(msg.isRead, true);
        expect(msg.transportId, 'tr-42');
        expect(msg.hasFailed, false);
      });

      test('handles null values with defaults', () {
        final json = <String, dynamic>{
          'id': null,
          'senderId': null,
          'senderName': null,
          'receiverId': null,
          'text': null,
          'timestamp': null,
          'isRead': null,
          'transportId': null,
          'hasFailed': null,
        };
        final msg = Message.fromJson(json);
        expect(msg.id, '');
        expect(msg.senderId, '');
        expect(msg.senderName, '');
        expect(msg.receiverId, '');
        expect(msg.text, '');
        expect(msg.timestamp, isA<DateTime>());
        expect(msg.isRead, false);
        expect(msg.transportId, isNull);
        expect(msg.hasFailed, false);
      });

      test('handles missing keys with defaults', () {
        final msg = Message.fromJson(<String, dynamic>{});
        expect(msg.id, '');
        expect(msg.senderId, '');
        expect(msg.text, '');
        expect(msg.isRead, false);
        expect(msg.transportId, isNull);
        expect(msg.hasFailed, false);
        expect(msg.timestamp, isA<DateTime>());
      });

      test('handles wrong types gracefully', () {
        // `as String?` on int/bool throws TypeError at runtime
        expect(
          () => Message.fromJson({
            'id': 123,
            'senderId': true,
            'senderName': null,
            'receiverId': 45.6,
            'text': [],
            'isRead': 'notabool',
            'hasFailed': 'notabool',
            'transportId': false,
          }),
          throwsA(isA<TypeError>()),
        );
      });

      test('parses DateTime from int milliseconds', () {
        final ms = DateTime.utc(2024, 6, 15, 10, 30).millisecondsSinceEpoch;
        final json = {
          'id': 'm',
          'senderId': 's',
          'senderName': 'S',
          'receiverId': 'r',
          'text': 'T',
          'timestamp': ms,
        };
        final msg = Message.fromJson(json);
        expect(
          msg.timestamp,
          DateTime.fromMillisecondsSinceEpoch(ms),
        );
      });

      test('parses DateTime from int seconds', () {
        final seconds =
            DateTime.utc(2024, 6, 15).millisecondsSinceEpoch ~/ 1000;
        final json = {
          'id': 'm',
          'senderId': 's',
          'senderName': 'S',
          'receiverId': 'r',
          'text': 'T',
          'timestamp': seconds,
        };
        final msg = Message.fromJson(json);
        expect(
          msg.timestamp,
          DateTime.fromMillisecondsSinceEpoch(seconds * 1000),
        );
      });

      test('parses DateTime from ISO string', () {
        final json = {
          'id': 'm',
          'senderId': 's',
          'senderName': 'S',
          'receiverId': 'r',
          'text': 'T',
          'timestamp': '2024-12-25T08:00:00.000Z',
        };
        final msg = Message.fromJson(json);
        expect(msg.timestamp, DateTime.utc(2024, 12, 25, 8, 0));
      });

      test('handles empty strings', () {
        final json = {
          'id': '',
          'senderId': '',
          'senderName': '',
          'receiverId': '',
          'text': '',
          'timestamp': '2024-01-01T00:00:00.000',
        };
        final msg = Message.fromJson(json);
        expect(msg.id, '');
        expect(msg.text, '');
      });

      test('handles isRead as true', () {
        final json = {
          'id': 'm',
          'senderId': 's',
          'senderName': 'S',
          'receiverId': 'r',
          'text': 'T',
          'timestamp': '2024-01-01T00:00:00.000',
          'isRead': true,
        };
        final msg = Message.fromJson(json);
        expect(msg.isRead, true);
      });

      test('handles hasFailed as true', () {
        final json = {
          'id': 'm',
          'senderId': 's',
          'senderName': 'S',
          'receiverId': 'r',
          'text': 'T',
          'timestamp': '2024-01-01T00:00:00.000',
          'hasFailed': true,
        };
        final msg = Message.fromJson(json);
        expect(msg.hasFailed, true);
      });
    });

    // ---------------------------------------------------------------------------
    // toJson
    // ---------------------------------------------------------------------------
    group('toJson', () {
      test('produces correct map', () {
        final msg = Message(
          id: 'msg-1',
          senderId: 'user-1',
          senderName: 'John Doe',
          receiverId: 'user-2',
          text: 'Hello!',
          timestamp: DateTime.utc(2024, 6, 15, 10, 30),
          isRead: true,
          transportId: 'tr-42',
          hasFailed: false,
        );
        final json = msg.toJson();
        expect(json['id'], 'msg-1');
        expect(json['senderId'], 'user-1');
        expect(json['senderName'], 'John Doe');
        expect(json['receiverId'], 'user-2');
        expect(json['text'], 'Hello!');
        expect(json['timestamp'], '2024-06-15T10:30:00.000Z');
        expect(json['isRead'], true);
        expect(json['transportId'], 'tr-42');
        expect(json['hasFailed'], false);
      });

      test('round-trip fromJson → toJson produces same map', () {
        final original = {
          'id': 'rt-1',
          'senderId': 's-1',
          'senderName': 'Jane',
          'receiverId': 'r-1',
          'text': 'Message text',
          'timestamp': '2024-08-10T12:00:00.000Z',
          'isRead': false,
          'transportId': null,
          'hasFailed': true,
        };
        final msg = Message.fromJson(original);
        final output = msg.toJson();
        expect(output['id'], 'rt-1');
        expect(output['senderId'], 's-1');
        expect(output['senderName'], 'Jane');
        expect(output['receiverId'], 'r-1');
        expect(output['text'], 'Message text');
        expect(output['timestamp'], '2024-08-10T12:00:00.000Z');
        expect(output['isRead'], false);
        expect(output['transportId'], isNull);
        expect(output['hasFailed'], true);
      });

      test('omits transportId when null', () {
        final msg = Message(
          id: 'm',
          senderId: 's',
          senderName: 'S',
          receiverId: 'r',
          text: 'T',
          timestamp: DateTime.utc(2024, 1, 1),
        );
        final json = msg.toJson();
        expect(json['transportId'], isNull);
      });
    });

    // ---------------------------------------------------------------------------
    // copyWith
    // ---------------------------------------------------------------------------
    group('copyWith', () {
      test('returns same object when no arguments', () {
        final msg = Message(
          id: 'm',
          senderId: 's',
          senderName: 'S',
          receiverId: 'r',
          text: 'T',
          timestamp: DateTime.utc(2024, 1, 1),
        );
        expect(msg.copyWith(), msg);
      });

      test('overrides specified fields', () {
        final msg = Message(
          id: 'm',
          senderId: 's',
          senderName: 'Old',
          receiverId: 'r',
          text: 'Old text',
          timestamp: DateTime.utc(2024, 1, 1),
        );
        final copy = msg.copyWith(
          senderName: 'New',
          text: 'New text',
          isRead: true,
          hasFailed: true,
        );
        expect(copy.senderName, 'New');
        expect(copy.text, 'New text');
        expect(copy.isRead, true);
        expect(copy.hasFailed, true);
        expect(copy.id, 'm');
      });
    });

    // ---------------------------------------------------------------------------
    // Equality
    // ---------------------------------------------------------------------------
    group('equality', () {
      test('same values are equal', () {
        final a = Message(
          id: 'm1',
          senderId: 's1',
          senderName: 'N',
          receiverId: 'r1',
          text: 'T',
          timestamp: DateTime.utc(2024, 1, 1),
        );
        final b = Message(
          id: 'm1',
          senderId: 's1',
          senderName: 'N',
          receiverId: 'r1',
          text: 'T',
          timestamp: DateTime.utc(2024, 1, 1),
        );
        expect(a, b);
        expect(a.hashCode, b.hashCode);
      });

      test('different ids are not equal', () {
        final a = Message(
          id: 'm1',
          senderId: 's1',
          senderName: 'N',
          receiverId: 'r1',
          text: 'T',
          timestamp: DateTime.utc(2024, 1, 1),
        );
        final b = Message(
          id: 'm2',
          senderId: 's1',
          senderName: 'N',
          receiverId: 'r1',
          text: 'T',
          timestamp: DateTime.utc(2024, 1, 1),
        );
        expect(a, isNot(b));
      });
    });

    // ---------------------------------------------------------------------------
    // toString
    // ---------------------------------------------------------------------------
    group('toString', () {
      test('includes key fields', () {
        final msg = Message(
          id: 'msg-1',
          senderId: 's',
          senderName: 'John Doe',
          receiverId: 'r',
          text: 'Hello!',
          timestamp: DateTime.utc(2024, 1, 1),
        );
        final str = msg.toString();
        expect(str, contains('msg-1'));
        expect(str, contains('John Doe'));
      });
    });
  });
}
