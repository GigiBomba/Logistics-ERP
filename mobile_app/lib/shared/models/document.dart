DateTime? _parseDateTime(dynamic value) {
  if (value is int) {
    return DateTime.fromMillisecondsSinceEpoch(
        value > 1e12 ? value : value * 1000);
  }
  if (value is String) return DateTime.tryParse(value);
  return null;
}

class Document {
  final String id;
  final String transportId;
  final String type; // cmr, pod, invoice, other
  final String fileName;
  final String fileUrl;
  final String uploadStatus; // pending, uploading, uploaded, failed
  final DateTime? uploadedAt;
  final Map<String, dynamic>? ocrData;

  const Document({
    required this.id,
    required this.transportId,
    required this.type,
    required this.fileName,
    required this.fileUrl,
    this.uploadStatus = 'pending',
    this.uploadedAt,
    this.ocrData,
  });

  factory Document.fromJson(Map<String, dynamic> json) {
    return Document(
      id: json['id'] as String? ?? '',
      transportId: json['transportId'] as String? ?? '',
      type: json['type'] as String? ?? '',
      fileName: json['fileName'] as String? ?? '',
      fileUrl: json['fileUrl'] as String? ?? '',
      uploadStatus: json['uploadStatus'] as String? ?? 'pending',
      uploadedAt: _parseDateTime(json['uploadedAt']),
      ocrData: json['ocrData'] is Map
          ? Map<String, dynamic>.from(json['ocrData'] as Map)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'transportId': transportId,
      'type': type,
      'fileName': fileName,
      'fileUrl': fileUrl,
      'uploadStatus': uploadStatus,
      'uploadedAt': uploadedAt?.toIso8601String(),
      'ocrData': ocrData,
    };
  }

  Document copyWith({
    String? id,
    String? transportId,
    String? type,
    String? fileName,
    String? fileUrl,
    String? uploadStatus,
    DateTime? uploadedAt,
    Map<String, dynamic>? ocrData,
  }) {
    return Document(
      id: id ?? this.id,
      transportId: transportId ?? this.transportId,
      type: type ?? this.type,
      fileName: fileName ?? this.fileName,
      fileUrl: fileUrl ?? this.fileUrl,
      uploadStatus: uploadStatus ?? this.uploadStatus,
      uploadedAt: uploadedAt ?? this.uploadedAt,
      ocrData: ocrData ?? this.ocrData,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Document &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          transportId == other.transportId &&
          type == other.type &&
          fileName == other.fileName &&
          fileUrl == other.fileUrl &&
          uploadStatus == other.uploadStatus &&
          uploadedAt == other.uploadedAt &&
          _mapEquals(ocrData, other.ocrData);

  @override
  int get hashCode => Object.hash(
        id,
        transportId,
        type,
        fileName,
        fileUrl,
        uploadStatus,
        uploadedAt,
        ocrData,
      );

  @override
  String toString() =>
      'Document(id: $id, transportId: $transportId, type: $type, '
      'fileName: $fileName, uploadStatus: $uploadStatus)';

  /// Deep equality helper for nullable maps.
  static bool _mapEquals(
    Map<String, dynamic>? a,
    Map<String, dynamic>? b,
  ) {
    if (a == null && b == null) return true;
    if (a == null || b == null) return false;
    if (a.length != b.length) return false;
    return a.entries.every((e) => b[e.key] == e.value);
  }
}
