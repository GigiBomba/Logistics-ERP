DateTime? _parseDateTime(dynamic value) {
  if (value is int) {
    return DateTime.fromMillisecondsSinceEpoch(
        value > 1e12 ? value : value * 1000);
  }
  if (value is String) return DateTime.tryParse(value);
  return null;
}

class Driver {
  final String id;
  final String companyId;
  final String userId;
  final String fullName;
  final String phone;
  final String status; // available, driving, off
  final String? currentTransportId;
  final String? currentVehicleId;
  final DateTime? lastActivity;

  const Driver({
    required this.id,
    required this.companyId,
    required this.userId,
    required this.fullName,
    required this.phone,
    this.status = 'available',
    this.currentTransportId,
    this.currentVehicleId,
    this.lastActivity,
  });

  factory Driver.fromJson(Map<String, dynamic> json) {
    return Driver(
      id: json['id'] as String? ?? '',
      companyId: json['companyId'] as String? ?? '',
      userId: json['userId'] as String? ?? '',
      fullName: json['fullName'] as String? ?? '',
      phone: json['phone'] as String? ?? '',
      status: json['status'] as String? ?? 'available',
      currentTransportId: json['currentTransportId'] as String?,
      currentVehicleId: json['currentVehicleId'] as String?,
      lastActivity: _parseDateTime(json['lastActivity']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'companyId': companyId,
      'userId': userId,
      'fullName': fullName,
      'phone': phone,
      'status': status,
      'currentTransportId': currentTransportId,
      'currentVehicleId': currentVehicleId,
      'lastActivity': lastActivity?.toIso8601String(),
    };
  }

  Driver copyWith({
    String? id,
    String? companyId,
    String? userId,
    String? fullName,
    String? phone,
    String? status,
    String? currentTransportId,
    String? currentVehicleId,
    DateTime? lastActivity,
  }) {
    return Driver(
      id: id ?? this.id,
      companyId: companyId ?? this.companyId,
      userId: userId ?? this.userId,
      fullName: fullName ?? this.fullName,
      phone: phone ?? this.phone,
      status: status ?? this.status,
      currentTransportId: currentTransportId ?? this.currentTransportId,
      currentVehicleId: currentVehicleId ?? this.currentVehicleId,
      lastActivity: lastActivity ?? this.lastActivity,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Driver &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          companyId == other.companyId &&
          userId == other.userId &&
          fullName == other.fullName &&
          phone == other.phone &&
          status == other.status &&
          currentTransportId == other.currentTransportId &&
          currentVehicleId == other.currentVehicleId &&
          lastActivity == other.lastActivity;

  @override
  int get hashCode => Object.hash(
        id,
        companyId,
        userId,
        fullName,
        phone,
        status,
        currentTransportId,
        currentVehicleId,
        lastActivity,
      );

  @override
  String toString() =>
      'Driver(id: $id, fullName: $fullName, phone: $phone, '
      'status: $status)';
}
