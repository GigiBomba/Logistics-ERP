import 'package:dio/dio.dart';

import '../api_client.dart';

/// Endpoint methods for document uploads.
class DocumentEndpoints {
  final ApiClient client;

  DocumentEndpoints(this.client);

  /// Upload a document associated with a transport.
  ///
  /// [transportId] identifies the related transport.
  /// [docType] is the document category (e.g. "pod", "invoice").
  /// [filePath] is the absolute path to the file on disk.
  Future<Response> uploadDocument(
    String transportId,
    String docType,
    String filePath,
  ) {
    final formData = FormData.fromMap({
      'transport_id': transportId,
      'document_type': docType,
      'file': MultipartFile.fromFileSync(filePath),
    });
    return client.upload('/api/v1/mobile/documents/upload', formData);
  }
}
