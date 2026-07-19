class User {
  final String id;
  final String email;
  final String fullName;
  final String role; // 'driver', 'dispatcher', 'fleet_manager', 'admin'
  final String companyId;
  final String? phone;
  final String? avatarUrl;

  const User({
    required this.id,
    required this.email,
    required this.fullName,
    required this.role,
    required this.companyId,
    this.phone,
    this.avatarUrl,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    // Handle both camelCase and snake_case from the backend.
    String? id;
    final rawId = json['id'];
    if (rawId is int) {
      id = rawId.toString();
    } else if (rawId is String) {
      id = rawId;
    }

    String? companyId;
    final rawCompanyId = json['companyId'] ?? json['company_id'];
    if (rawCompanyId is int) {
      companyId = rawCompanyId.toString();
    } else if (rawCompanyId is String) {
      companyId = rawCompanyId;
    }

    return User(
      id: id ?? '',
      email: json['email'] as String? ?? '',
      fullName: (json['fullName'] is String
          ? json['fullName'] as String
          : json['display_name'] is String
              ? json['display_name'] as String
              : json['fullName']?.toString() ?? ''),
      role: json['role'] as String? ?? '',
      companyId: companyId ?? '',
      phone: json['phone'] as String?,
      avatarUrl: json['avatarUrl'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'fullName': fullName,
      'role': role,
      'companyId': companyId,
      'phone': phone,
      'avatarUrl': avatarUrl,
    };
  }

  User copyWith({
    String? id,
    String? email,
    String? fullName,
    String? role,
    String? companyId,
    String? phone,
    String? avatarUrl,
  }) {
    return User(
      id: id ?? this.id,
      email: email ?? this.email,
      fullName: fullName ?? this.fullName,
      role: role ?? this.role,
      companyId: companyId ?? this.companyId,
      phone: phone ?? this.phone,
      avatarUrl: avatarUrl ?? this.avatarUrl,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is User &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          email == other.email &&
          fullName == other.fullName &&
          role == other.role &&
          companyId == other.companyId &&
          phone == other.phone &&
          avatarUrl == other.avatarUrl;

  @override
  int get hashCode =>
      Object.hash(id, email, fullName, role, companyId, phone, avatarUrl);

  @override
  String toString() =>
      'User(id: $id, email: $email, fullName: $fullName, role: $role, '
      'companyId: $companyId, phone: $phone, avatarUrl: $avatarUrl)';
}
