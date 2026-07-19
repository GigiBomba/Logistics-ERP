/// A real-time position of a vehicle in the fleet.
///
/// Maps to the `GET /fleet/positions` API response where each item contains:
/// `vehicle_id`, `plate`, `driver_name`, `lat`, `lng`, `status`, `last_update`.
DateTime _parseDateTime(dynamic value) {
  if (value is int) {
    return DateTime.fromMillisecondsSinceEpoch(
        value > 1e12 ? value : value * 1000);
  }
  if (value is String) {
    return DateTime.tryParse(value) ?? DateTime.now();
  }
  return DateTime.now();
}

class FleetPosition {
  final String vehicleId;
  final String plate;
  final String driverName;
  final double latitude;
  final double longitude;
  final String status;
  final DateTime lastUpdate;

  const FleetPosition({
    required this.vehicleId,
    required this.plate,
    required this.driverName,
    required this.latitude,
    required this.longitude,
    required this.status,
    required this.lastUpdate,
  });

  factory FleetPosition.fromJson(Map<String, dynamic> json) {
    return FleetPosition(
      vehicleId: json['vehicle_id'] as String? ?? '',
      plate: json['plate'] as String? ?? '',
      driverName: json['driver_name'] as String? ?? '',
      latitude: (json['lat'] as num?)?.toDouble() ?? 0.0,
      longitude: (json['lng'] as num?)?.toDouble() ?? 0.0,
      status: json['status'] as String? ?? '',
      lastUpdate: _parseDateTime(json['last_update']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'vehicle_id': vehicleId,
      'plate': plate,
      'driver_name': driverName,
      'lat': latitude,
      'lng': longitude,
      'status': status,
      'last_update': lastUpdate.toIso8601String(),
    };
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is FleetPosition &&
          runtimeType == other.runtimeType &&
          vehicleId == other.vehicleId &&
          plate == other.plate &&
          driverName == other.driverName &&
          latitude == other.latitude &&
          longitude == other.longitude &&
          status == other.status &&
          lastUpdate == other.lastUpdate;

  @override
  int get hashCode => Object.hash(
        vehicleId,
        plate,
        driverName,
        latitude,
        longitude,
        status,
        lastUpdate,
      );

  @override
  String toString() =>
      'FleetPosition(vehicleId: $vehicleId, plate: $plate, '
      'driverName: $driverName, status: $status, '
      'lat: $latitude, lng: $longitude)';
}
