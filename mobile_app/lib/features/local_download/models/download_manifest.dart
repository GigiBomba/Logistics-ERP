/// Download category enum matching the backend DownloadCategory.
enum DownloadCategory {
  documents,
  invoices,
  receipts,
  ocrResults,
  tripHistory;

  String get displayKey {
    switch (this) {
      case DownloadCategory.documents: return 'localDownload_categoryDocuments';
      case DownloadCategory.invoices: return 'localDownload_categoryInvoices';
      case DownloadCategory.receipts: return 'localDownload_categoryReceipts';
      case DownloadCategory.ocrResults: return 'localDownload_categoryOcrResults';
      case DownloadCategory.tripHistory: return 'localDownload_categoryTripHistory';
    }
  }
}

/// A single downloadable record from the manifest.
class DownloadManifestEntry {
  final String recordId;
  final String filename;
  final int sizeBytes;
  final String downloadUrl;
  final DateTime urlExpiresAt;

  const DownloadManifestEntry({
    required this.recordId,
    required this.filename,
    required this.sizeBytes,
    required this.downloadUrl,
    required this.urlExpiresAt,
  });

  factory DownloadManifestEntry.fromJson(Map<String, dynamic> json) =>
      DownloadManifestEntry(
        recordId: json['record_id'] as String? ?? '',
        filename: json['filename'] as String? ?? '',
        sizeBytes: json['size_bytes'] as int? ?? 0,
        downloadUrl: json['download_url'] as String? ?? '',
        urlExpiresAt: json['url_expires_at'] != null
            ? DateTime.parse(json['url_expires_at'] as String)
            : DateTime.now(),
      );

  Map<String, dynamic> toJson() => {
    'record_id': recordId,
    'filename': filename,
    'size_bytes': sizeBytes,
    'download_url': downloadUrl,
    'url_expires_at': urlExpiresAt.toIso8601String(),
  };
}
