import 'vehicle_document.dart';

DateTime? _parseDateTime(dynamic value) {
  if (value is int) {
    return DateTime.fromMillisecondsSinceEpoch(
        value > 1e12 ? value : value * 1000);
  }
  if (value is String) return DateTime.tryParse(value);
  return null;
}

class Vehicle {
  final String id;
  final String companyId;
  final String plate;
  final String type;
  final String brand;
  final String model;
  final String status;
  final String? assignedDriverId;
  final List<VehicleDocument> documents;
  final DateTime? lastUpdated;

  const Vehicle({
    required this.id,
    required this.companyId,
    required this.plate,
    required this.type,
    required this.brand,
    required this.model,
    required this.status,
    this.assignedDriverId,
    this.documents = const [],
    this.lastUpdated,
  });

  factory Vehicle.fromJson(Map<String, dynamic> json) {
    return Vehicle(
      id: json['id'] as String? ?? '',
      companyId: json['companyId'] as String? ?? '',
      plate: json['plate'] as String? ?? '',
      type: json['type'] as String? ?? '',
      brand: json['brand'] as String? ?? '',
      model: json['model'] as String? ?? '',
      status: json['status'] as String? ?? '',
      assignedDriverId: json['assignedDriverId'] as String?,
      documents: (json['documents'] as List<dynamic>?)
              ?.map(
                (e) => VehicleDocument.fromJson(e as Map<String, dynamic>),
              )
              .toList() ??
          [],
      lastUpdated: _parseDateTime(json['lastUpdated']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'companyId': companyId,
      'plate': plate,
      'type': type,
      'brand': brand,
      'model': model,
      'status': status,
      'assignedDriverId': assignedDriverId,
      'documents': documents.map((d) => d.toJson()).toList(),
      'lastUpdated': lastUpdated?.toIso8601String(),
    };
  }

  Vehicle copyWith({
    String? id,
    String? companyId,
    String? plate,
    String? type,
    String? brand,
    String? model,
    String? status,
    String? assignedDriverId,
    List<VehicleDocument>? documents,
    DateTime? lastUpdated,
  }) {
    return Vehicle(
      id: id ?? this.id,
      companyId: companyId ?? this.companyId,
      plate: plate ?? this.plate,
      type: type ?? this.type,
      brand: brand ?? this.brand,
      model: model ?? this.model,
      status: status ?? this.status,
      assignedDriverId: assignedDriverId ?? this.assignedDriverId,
      documents: documents ?? this.documents,
      lastUpdated: lastUpdated ?? this.lastUpdated,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Vehicle &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          companyId == other.companyId &&
          plate == other.plate &&
          type == other.type &&
          brand == other.brand &&
          model == other.model &&
          status == other.status &&
          assignedDriverId == other.assignedDriverId &&
          documents == other.documents &&
          lastUpdated == other.lastUpdated;

  @override
  int get hashCode => Object.hash(
        id,
        companyId,
        plate,
        type,
        brand,
        model,
        status,
        assignedDriverId,
        Object.hashAll(documents),
        lastUpdated,
      );

  @override
  String toString() =>
      'Vehicle(id: $id, plate: $plate, brand: $brand, model: $model, '
      'type: $type, status: $status)';
}
