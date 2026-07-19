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

class Alert {
  final String id;
  final String companyId;
  final String type; // delay, maintenance, document_expiry, compliance
  final String title;
  final String description;
  final String severity; // low, medium, high, critical
  final bool isRead;
  final DateTime createdAt;
  final String? relatedEntityId;
  final String? relatedEntityType;

  const Alert({
    required this.id,
    required this.companyId,
    required this.type,
    required this.title,
    required this.description,
    this.severity = 'medium',
    this.isRead = false,
    required this.createdAt,
    this.relatedEntityId,
    this.relatedEntityType,
  });

  factory Alert.fromJson(Map<String, dynamic> json) {
    return Alert(
      id: json['id'] as String? ?? '',
      companyId: json['companyId'] as String? ?? '',
      type: json['type'] as String? ?? '',
      title: json['title'] as String? ?? '',
      description: json['description'] as String? ?? '',
      severity: json['severity'] as String? ?? 'medium',
      isRead: json['isRead'] as bool? ?? false,
      createdAt: _parseDateTime(json['createdAt']),
      relatedEntityId: json['relatedEntityId'] as String?,
      relatedEntityType: json['relatedEntityType'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'companyId': companyId,
      'type': type,
      'title': title,
      'description': description,
      'severity': severity,
      'isRead': isRead,
      'createdAt': createdAt.toIso8601String(),
      'relatedEntityId': relatedEntityId,
      'relatedEntityType': relatedEntityType,
    };
  }

  Alert copyWith({
    String? id,
    String? companyId,
    String? type,
    String? title,
    String? description,
    String? severity,
    bool? isRead,
    DateTime? createdAt,
    String? relatedEntityId,
    String? relatedEntityType,
  }) {
    return Alert(
      id: id ?? this.id,
      companyId: companyId ?? this.companyId,
      type: type ?? this.type,
      title: title ?? this.title,
      description: description ?? this.description,
      severity: severity ?? this.severity,
      isRead: isRead ?? this.isRead,
      createdAt: createdAt ?? this.createdAt,
      relatedEntityId: relatedEntityId ?? this.relatedEntityId,
      relatedEntityType: relatedEntityType ?? this.relatedEntityType,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Alert &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          companyId == other.companyId &&
          type == other.type &&
          title == other.title &&
          description == other.description &&
          severity == other.severity &&
          isRead == other.isRead &&
          createdAt == other.createdAt &&
          relatedEntityId == other.relatedEntityId &&
          relatedEntityType == other.relatedEntityType;

  @override
  int get hashCode => Object.hash(
        id,
        companyId,
        type,
        title,
        description,
        severity,
        isRead,
        createdAt,
        relatedEntityId,
        relatedEntityType,
      );

  @override
  String toString() =>
      'Alert(id: $id, type: $type, title: $title, severity: $severity, '
      'isRead: $isRead)';
}
