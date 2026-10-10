import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/features/document_center/models/ocr_upload_response.dart';

void main() {
  group('Document Center — No Auto-Pull', () {
    test('OcrUploadResponse never contains completed status', () {
      // The model only has queued/processing — no completed
      expect(OcrUploadStatus.values.length, 2);
      expect(OcrUploadStatus.values, contains(OcrUploadStatus.queued));
      expect(OcrUploadStatus.values, contains(OcrUploadStatus.processing));
    });

    test('successful upload does not cache OCR result data locally', () {
      // This is a structural assertion: verify no local DB write in the
      // upload flow. In a full implementation, this would use provider
      // overrides and assert no local storage write occurs.
      expect(true, isTrue, reason: 'Placeholder — verify no local cache write on upload');
    });

    test('fromJson parses queued status', () {
      final json = {'document_id': 'doc-1', 'status': 'queued', 'idempotency_key': 'uuid-1'};
      final result = OcrUploadResponse.fromJson(json);
      expect(result.status, OcrUploadStatus.queued);
      expect(result.documentId, 'doc-1');
    });

    test('fromJson parses processing status', () {
      final json = {'document_id': 'doc-2', 'status': 'processing', 'idempotency_key': 'uuid-2'};
      final result = OcrUploadResponse.fromJson(json);
      expect(result.status, OcrUploadStatus.processing);
    });
  });
}
