/// Status returned by the OCR processing endpoint.
enum OcrUploadStatus { queued, processing }

/// Response from POST /api/v1/ocr/process.
///
/// The status is always `queued` or `processing` — never `completed`
/// synchronously. OCR results stay server-side until Local Download pulls them.
class OcrUploadResponse {
  final String documentId;
  final OcrUploadStatus status;
  final String idempotencyKey;

  const OcrUploadResponse({
    required this.documentId,
    required this.status,
    required this.idempotencyKey,
  });

  factory OcrUploadResponse.fromJson(Map<String, dynamic> json) =>
      OcrUploadResponse(
        documentId: json['document_id'] as String? ?? '',
        status: json['status'] == 'processing'
            ? OcrUploadStatus.processing
            : OcrUploadStatus.queued,
        idempotencyKey: json['idempotency_key'] as String? ?? '',
      );

  Map<String, dynamic> toJson() => {
    'document_id': documentId,
    'status': status.name,
    'idempotency_key': idempotencyKey,
  };
}
