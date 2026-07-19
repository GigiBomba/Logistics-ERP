DateTime? _parseDateTime(dynamic value) {
  if (value is int) {
    return DateTime.fromMillisecondsSinceEpoch(
        value > 1e12 ? value : value * 1000);
  }
  if (value is String) return DateTime.tryParse(value);
  return null;
}

class VehicleDocument {
  final String id;
  final String vehicleId;
  final String documentType; // ITP, RCA, CASCO, etc.
  final DateTime? expiryDate;
  final bool isExpiringSoon;

  const VehicleDocument({
    required this.id,
    required this.vehicleId,
    required this.documentType,
    this.expiryDate,
    this.isExpiringSoon = false,
  });

  factory VehicleDocument.fromJson(Map<String, dynamic> json) {
    return VehicleDocument(
      id: json['id'] as String? ?? '',
      vehicleId: json['vehicleId'] as String? ?? '',
      documentType: json['documentType'] as String? ?? '',
      expiryDate: _parseDateTime(json['expiryDate']),
      isExpiringSoon: json['isExpiringSoon'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'vehicleId': vehicleId,
      'documentType': documentType,
      'expiryDate': expiryDate?.toIso8601String(),
      'isExpiringSoon': isExpiringSoon,
    };
  }

  VehicleDocument copyWith({
    String? id,
    String? vehicleId,
    String? documentType,
    DateTime? expiryDate,
    bool? isExpiringSoon,
  }) {
    return VehicleDocument(
      id: id ?? this.id,
      vehicleId: vehicleId ?? this.vehicleId,
      documentType: documentType ?? this.documentType,
      expiryDate: expiryDate ?? this.expiryDate,
      isExpiringSoon: isExpiringSoon ?? this.isExpiringSoon,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is VehicleDocument &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          vehicleId == other.vehicleId &&
          documentType == other.documentType &&
          expiryDate == other.expiryDate &&
          isExpiringSoon == other.isExpiringSoon;

  @override
  int get hashCode =>
      Object.hash(id, vehicleId, documentType, expiryDate, isExpiringSoon);

  @override
  String toString() =>
      'VehicleDocument(id: $id, vehicleId: $vehicleId, '
      'documentType: $documentType, expiryDate: $expiryDate, '
      'isExpiringSoon: $isExpiringSoon)';
}
