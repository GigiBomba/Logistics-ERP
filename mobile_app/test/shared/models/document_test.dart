import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/shared/models/document.dart';

void main() {
  group('Document', () {
    // ---------------------------------------------------------------------------
    // fromJson
    // ---------------------------------------------------------------------------
    group('fromJson', () {
      test('parses valid JSON correctly', () {
        final json = {
          'id': 'doc-1',
          'transportId': 'tr-42',
          'type': 'cmr',
          'fileName': 'cmr_scan.pdf',
          'fileUrl': 'https://storage.example.com/cmr_scan.pdf',
          'uploadStatus': 'uploaded',
          'uploadedAt': '2024-06-15T10:30:00.000Z',
          'ocrData': {'reference': 'REF-001', 'amount': 1500.0},
        };
        final doc = Document.fromJson(json);
        expect(doc.id, 'doc-1');
        expect(doc.transportId, 'tr-42');
        expect(doc.type, 'cmr');
        expect(doc.fileName, 'cmr_scan.pdf');
        expect(doc.fileUrl, 'https://storage.example.com/cmr_scan.pdf');
        expect(doc.uploadStatus, 'uploaded');
        expect(doc.uploadedAt, DateTime.utc(2024, 6, 15, 10, 30));
        expect(doc.ocrData, {'reference': 'REF-001', 'amount': 1500.0});
      });

      test('handles null values with defaults', () {
        final json = <String, dynamic>{
          'id': null,
          'transportId': null,
          'type': null,
          'fileName': null,
          'fileUrl': null,
          'uploadStatus': null,
          'uploadedAt': null,
          'ocrData': null,
        };
        final doc = Document.fromJson(json);
        expect(doc.id, '');
        expect(doc.transportId, '');
        expect(doc.type, '');
        expect(doc.fileName, '');
        expect(doc.fileUrl, '');
        expect(doc.uploadStatus, 'pending');
        expect(doc.uploadedAt, isNull);
        expect(doc.ocrData, isNull);
      });

      test('handles missing keys with defaults', () {
        final doc = Document.fromJson(<String, dynamic>{});
        expect(doc.id, '');
        expect(doc.uploadStatus, 'pending');
        expect(doc.uploadedAt, isNull);
        expect(doc.ocrData, isNull);
      });

      test('handles wrong types gracefully', () {
        // `as String?` on int/bool throws TypeError at runtime
        expect(
          () => Document.fromJson({
            'id': 123,
            'transportId': true,
            'type': null,
            'fileName': 45.6,
            'fileUrl': [],
            'uploadStatus': 1,
          }),
          throwsA(isA<TypeError>()),
        );
      });

      test('parses DateTime from int milliseconds', () {
        final ms = DateTime.utc(2024, 1, 15).millisecondsSinceEpoch;
        final json = {
          'id': 'd',
          'transportId': 't',
          'type': 'pod',
          'fileName': 'f',
          'fileUrl': 'u',
          'uploadedAt': ms,
        };
        final doc = Document.fromJson(json);
        expect(
          doc.uploadedAt,
          DateTime.fromMillisecondsSinceEpoch(ms),
        );
      });

      test('parses DateTime from int seconds', () {
        final seconds = DateTime.utc(2024, 6, 15).millisecondsSinceEpoch ~/ 1000;
        final json = {
          'id': 'd',
          'transportId': 't',
          'type': 'pod',
          'fileName': 'f',
          'fileUrl': 'u',
          'uploadedAt': seconds,
        };
        final doc = Document.fromJson(json);
        expect(
          doc.uploadedAt,
          DateTime.fromMillisecondsSinceEpoch(seconds * 1000),
        );
      });

      test('handles empty strings in fields', () {
        final json = {
          'id': '',
          'transportId': '',
          'type': '',
          'fileName': '',
          'fileUrl': '',
          'uploadStatus': '',
        };
        final doc = Document.fromJson(json);
        expect(doc.id, '');
        expect(doc.type, '');
        expect(doc.uploadStatus, ''); // empty overrides 'pending' default
      });

      test('handles ocrData as non-Map gracefully', () {
        final json = {
          'id': 'd',
          'transportId': 't',
          'type': 'other',
          'fileName': 'f',
          'fileUrl': 'u',
          'ocrData': 'string-value',
        };
        final doc = Document.fromJson(json);
        expect(doc.ocrData, isNull);
      });

      test('handles ocrData as empty map', () {
        final json = {
          'id': 'd',
          'transportId': 't',
          'type': 'other',
          'fileName': 'f',
          'fileUrl': 'u',
          'ocrData': <String, dynamic>{},
        };
        final doc = Document.fromJson(json);
        expect(doc.ocrData, <String, dynamic>{});
      });
    });

    // ---------------------------------------------------------------------------
    // toJson
    // ---------------------------------------------------------------------------
    group('toJson', () {
      test('produces correct map', () {
        final doc = Document(
          id: 'doc-1',
          transportId: 'tr-42',
          type: 'invoice',
          fileName: 'inv.pdf',
          fileUrl: 'https://example.com/inv.pdf',
          uploadStatus: 'uploaded',
          uploadedAt: DateTime.utc(2024, 7, 1, 12, 0),
          ocrData: {'total': 500.0},
        );
        final json = doc.toJson();
        expect(json['id'], 'doc-1');
        expect(json['transportId'], 'tr-42');
        expect(json['type'], 'invoice');
        expect(json['fileName'], 'inv.pdf');
        expect(json['fileUrl'], 'https://example.com/inv.pdf');
        expect(json['uploadStatus'], 'uploaded');
        expect(json['uploadedAt'], '2024-07-01T12:00:00.000Z');
        expect(json['ocrData'], {'total': 500.0});
      });

      test('round-trip fromJson → toJson produces same map', () {
        final original = {
          'id': 'rt-1',
          'transportId': 'tr-1',
          'type': 'cmr',
          'fileName': 'scan.pdf',
          'fileUrl': 'https://example.com/scan.pdf',
          'uploadStatus': 'uploading',
          'uploadedAt': '2024-08-15T09:00:00.000Z',
          'ocrData': {'field': 'value'},
        };
        final doc = Document.fromJson(original);
        final output = doc.toJson();
        expect(output['id'], 'rt-1');
        expect(output['transportId'], 'tr-1');
        expect(output['type'], 'cmr');
        expect(output['fileName'], 'scan.pdf');
        expect(output['uploadStatus'], 'uploading');
        expect(output['uploadedAt'], '2024-08-15T09:00:00.000Z');
        expect(output['ocrData'], {'field': 'value'});
      });

      test('omits uploadedAt when null', () {
        final doc = Document(
          id: 'd',
          transportId: 't',
          type: 'other',
          fileName: 'f',
          fileUrl: 'u',
        );
        final json = doc.toJson();
        expect(json['uploadedAt'], isNull);
      });

      test('omits ocrData when null', () {
        final doc = Document(
          id: 'd',
          transportId: 't',
          type: 'other',
          fileName: 'f',
          fileUrl: 'u',
        );
        final json = doc.toJson();
        expect(json['ocrData'], isNull);
      });
    });

    // ---------------------------------------------------------------------------
    // copyWith
    // ---------------------------------------------------------------------------
    group('copyWith', () {
      test('returns same object when no arguments', () {
        final doc = Document(
          id: 'd',
          transportId: 't',
          type: 'cmr',
          fileName: 'f',
          fileUrl: 'u',
        );
        expect(doc.copyWith(), doc);
      });

      test('overrides specified fields', () {
        final doc = Document(
          id: 'd',
          transportId: 't',
          type: 'cmr',
          fileName: 'f',
          fileUrl: 'u',
          uploadStatus: 'pending',
        );
        final copy = doc.copyWith(
          fileName: 'new.pdf',
          uploadStatus: 'uploaded',
        );
        expect(copy.id, 'd');
        expect(copy.fileName, 'new.pdf');
        expect(copy.uploadStatus, 'uploaded');
      });
    });

    // ---------------------------------------------------------------------------
    // Equality
    // ---------------------------------------------------------------------------
    group('equality', () {
      test('same values are equal', () {
        final a = Document(
          id: 'd1',
          transportId: 't1',
          type: 'cmr',
          fileName: 'f',
          fileUrl: 'u',
        );
        final b = Document(
          id: 'd1',
          transportId: 't1',
          type: 'cmr',
          fileName: 'f',
          fileUrl: 'u',
        );
        expect(a, b);
        expect(a.hashCode, b.hashCode);
      });

      test('different ids are not equal', () {
        final a = Document(
          id: 'd1',
          transportId: 't1',
          type: 'cmr',
          fileName: 'f',
          fileUrl: 'u',
        );
        final b = Document(
          id: 'd2',
          transportId: 't1',
          type: 'cmr',
          fileName: 'f',
          fileUrl: 'u',
        );
        expect(a, isNot(b));
      });
    });

    // ---------------------------------------------------------------------------
    // toString
    // ---------------------------------------------------------------------------
    group('toString', () {
      test('includes key fields', () {
        final doc = Document(
          id: 'doc-1',
          transportId: 'tr-42',
          type: 'cmr',
          fileName: 'scan.pdf',
          fileUrl: 'u',
        );
        final str = doc.toString();
        expect(str, contains('doc-1'));
        expect(str, contains('tr-42'));
        expect(str, contains('cmr'));
        expect(str, contains('scan.pdf'));
      });
    });
  });
}
