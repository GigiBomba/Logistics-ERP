DateTime? _parseDateTime(dynamic value) {
  if (value is int) {
    return DateTime.fromMillisecondsSinceEpoch(
        value > 1e12 ? value : value * 1000);
  }
  if (value is String) return DateTime.tryParse(value);
  return null;
}

class Transport {
  final String id;
  final String companyId;
  final String loadInfo;
  final String origin;
  final String destination;
  final List<String> waypoints;
  final String status; // planned, loading, in_transit, delivered, etc.
  final String? assignedDriverId;
  final String? assignedDriverName;
  final String? vehicleId;
  final String? vehiclePlate;
  final DateTime? scheduledDate;
  final DateTime? deliveredDate;
  final DateTime? lastUpdated;
  final double? originLat;
  final double? originLng;
  final double? destLat;
  final double? destLng;

  const Transport({
    required this.id,
    required this.companyId,
    required this.loadInfo,
    required this.origin,
    required this.destination,
    this.waypoints = const [],
    required this.status,
    this.assignedDriverId,
    this.assignedDriverName,
    this.vehicleId,
    this.vehiclePlate,
    this.scheduledDate,
    this.deliveredDate,
    this.lastUpdated,
    this.originLat,
    this.originLng,
    this.destLat,
    this.destLng,
  });

  factory Transport.fromJson(Map<String, dynamic> json) {
    return Transport(
      id: json['id'] as String? ?? '',
      companyId: json['companyId'] as String? ?? '',
      loadInfo: json['loadInfo'] as String? ?? '',
      origin: json['origin'] as String? ?? '',
      destination: json['destination'] as String? ?? '',
      waypoints: json['waypoints'] is List
          ? (json['waypoints'] as List).map((e) => e.toString()).toList()
          : [],
      status: json['status'] as String? ?? '',
      assignedDriverId: json['assignedDriverId'] as String?,
      assignedDriverName: json['assignedDriverName'] as String?,
      vehicleId: json['vehicleId'] as String?,
      vehiclePlate: json['vehiclePlate'] as String?,
      scheduledDate: _parseDateTime(json['scheduledDate']),
      deliveredDate: _parseDateTime(json['deliveredDate']),
      lastUpdated: _parseDateTime(json['lastUpdated']),
      originLat: (json['originLat'] as num?)?.toDouble(),
      originLng: (json['originLng'] as num?)?.toDouble(),
      destLat: (json['destLat'] as num?)?.toDouble(),
      destLng: (json['destLng'] as num?)?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'companyId': companyId,
      'loadInfo': loadInfo,
      'origin': origin,
      'destination': destination,
      'waypoints': waypoints,
      'status': status,
      'assignedDriverId': assignedDriverId,
      'assignedDriverName': assignedDriverName,
      'vehicleId': vehicleId,
      'vehiclePlate': vehiclePlate,
      'scheduledDate': scheduledDate?.toIso8601String(),
      'deliveredDate': deliveredDate?.toIso8601String(),
      'lastUpdated': lastUpdated?.toIso8601String(),
      'originLat': originLat,
      'originLng': originLng,
      'destLat': destLat,
      'destLng': destLng,
    };
  }

  Transport copyWith({
    String? id,
    String? companyId,
    String? loadInfo,
    String? origin,
    String? destination,
    List<String>? waypoints,
    String? status,
    String? assignedDriverId,
    String? assignedDriverName,
    String? vehicleId,
    String? vehiclePlate,
    DateTime? scheduledDate,
    DateTime? deliveredDate,
    DateTime? lastUpdated,
    double? originLat,
    double? originLng,
    double? destLat,
    double? destLng,
  }) {
    return Transport(
      id: id ?? this.id,
      companyId: companyId ?? this.companyId,
      loadInfo: loadInfo ?? this.loadInfo,
      origin: origin ?? this.origin,
      destination: destination ?? this.destination,
      waypoints: waypoints ?? this.waypoints,
      status: status ?? this.status,
      assignedDriverId: assignedDriverId ?? this.assignedDriverId,
      assignedDriverName: assignedDriverName ?? this.assignedDriverName,
      vehicleId: vehicleId ?? this.vehicleId,
      vehiclePlate: vehiclePlate ?? this.vehiclePlate,
      scheduledDate: scheduledDate ?? this.scheduledDate,
      deliveredDate: deliveredDate ?? this.deliveredDate,
      lastUpdated: lastUpdated ?? this.lastUpdated,
      originLat: originLat ?? this.originLat,
      originLng: originLng ?? this.originLng,
      destLat: destLat ?? this.destLat,
      destLng: destLng ?? this.destLng,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Transport &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          companyId == other.companyId &&
          loadInfo == other.loadInfo &&
          origin == other.origin &&
          destination == other.destination &&
          waypoints == other.waypoints &&
          status == other.status &&
          assignedDriverId == other.assignedDriverId &&
          assignedDriverName == other.assignedDriverName &&
          vehicleId == other.vehicleId &&
          vehiclePlate == other.vehiclePlate &&
          scheduledDate == other.scheduledDate &&
          deliveredDate == other.deliveredDate &&
          lastUpdated == other.lastUpdated &&
          originLat == other.originLat &&
          originLng == other.originLng &&
          destLat == other.destLat &&
          destLng == other.destLng;

  @override
  int get hashCode => Object.hash(
        id,
        companyId,
        loadInfo,
        origin,
        destination,
        Object.hashAll(waypoints),
        status,
        assignedDriverId,
        assignedDriverName,
        vehicleId,
        vehiclePlate,
        scheduledDate,
        deliveredDate,
        lastUpdated,
        originLat,
        originLng,
        destLat,
        destLng,
      );

  @override
  String toString() =>
      'Transport(id: $id, loadInfo: $loadInfo, origin: $origin, '
      'destination: $destination, status: $status, '
      'assignedDriverName: $assignedDriverName, vehiclePlate: $vehiclePlate)';
}
