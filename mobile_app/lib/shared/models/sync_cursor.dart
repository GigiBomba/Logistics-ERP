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

class SyncCursor {
  final DateTime lastSyncTimestamp;
  final String entityType;

  const SyncCursor({
    required this.lastSyncTimestamp,
    required this.entityType,
  });

  factory SyncCursor.fromJson(Map<String, dynamic> json) {
    return SyncCursor(
      lastSyncTimestamp: _parseDateTime(json['lastSyncTimestamp']),
      entityType: json['entityType'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'lastSyncTimestamp': lastSyncTimestamp.toIso8601String(),
      'entityType': entityType,
    };
  }

  SyncCursor copyWith({
    DateTime? lastSyncTimestamp,
    String? entityType,
  }) {
    return SyncCursor(
      lastSyncTimestamp: lastSyncTimestamp ?? this.lastSyncTimestamp,
      entityType: entityType ?? this.entityType,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SyncCursor &&
          runtimeType == other.runtimeType &&
          lastSyncTimestamp == other.lastSyncTimestamp &&
          entityType == other.entityType;

  @override
  int get hashCode => Object.hash(lastSyncTimestamp, entityType);

  @override
  String toString() =>
      'SyncCursor(lastSyncTimestamp: $lastSyncTimestamp, '
      'entityType: $entityType)';
}
