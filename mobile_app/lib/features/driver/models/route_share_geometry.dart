/// A single coordinate point along a transport route.
class RoutePoint {
  final double lat;
  final double lng;

  const RoutePoint({required this.lat, required this.lng});

  factory RoutePoint.fromJson(Map<String, dynamic> json) => RoutePoint(
    lat: (json['lat'] as num).toDouble(),
    lng: (json['lng'] as num).toDouble(),
  );

  Map<String, dynamic> toJson() => {'lat': lat, 'lng': lng};
}

/// A turn-by-turn instruction attached to a specific point on the route.
class RouteInstruction {
  final String textKey;
  final double distanceMeters;
  final int pointIndex;

  const RouteInstruction({
    required this.textKey,
    required this.distanceMeters,
    required this.pointIndex,
  });

  factory RouteInstruction.fromJson(Map<String, dynamic> json) =>
      RouteInstruction(
        textKey: json['text_key'] as String? ?? '',
        distanceMeters: (json['distance_meters'] as num?)?.toDouble() ?? 0,
        pointIndex: json['point_index'] as int? ?? 0,
      );

  Map<String, dynamic> toJson() => {
    'text_key': textKey,
    'distance_meters': distanceMeters,
    'point_index': pointIndex,
  };
}

/// Full route geometry and turn-by-turn instructions for a transport.
///
/// Fetched from `GET /api/v1/mobile/driver/transports/{transport_id}/route-share`.
class RouteShareGeometry {
  final String transportId;
  final List<RoutePoint> points;
  final List<RouteInstruction> instructions;
  final double totalDistanceMeters;
  final int totalDurationSeconds;
  final DateTime generatedAt;
  final int ttlSeconds;

  const RouteShareGeometry({
    required this.transportId,
    required this.points,
    this.instructions = const [],
    required this.totalDistanceMeters,
    required this.totalDurationSeconds,
    required this.generatedAt,
    required this.ttlSeconds,
  });

  /// Whether this geometry data is too old to use and should be re-fetched.
  bool get isStale =>
      DateTime.now().difference(generatedAt).inSeconds > ttlSeconds;

  factory RouteShareGeometry.fromJson(Map<String, dynamic> json) =>
      RouteShareGeometry(
        transportId: json['transport_id'] as String? ?? '',
        points: (json['points'] as List<dynamic>?)
                ?.map((e) => RoutePoint.fromJson(e as Map<String, dynamic>))
                .toList() ??
            const [],
        instructions: (json['instructions'] as List<dynamic>?)
                ?.map((e) =>
                    RouteInstruction.fromJson(e as Map<String, dynamic>))
                .toList() ??
            const [],
        totalDistanceMeters:
            (json['total_distance_meters'] as num?)?.toDouble() ?? 0,
        totalDurationSeconds: json['total_duration_seconds'] as int? ?? 0,
        generatedAt: json['generated_at'] != null
            ? DateTime.parse(json['generated_at'] as String)
            : DateTime.fromMillisecondsSinceEpoch(0), // sentinel epoch so isStale detects missing data
        ttlSeconds: json['ttl_seconds'] as int? ?? 300,
      );

  Map<String, dynamic> toJson() => {
    'transport_id': transportId,
    'points': points.map((p) => p.toJson()).toList(),
    'instructions': instructions.map((i) => i.toJson()).toList(),
    'total_distance_meters': totalDistanceMeters,
    'total_duration_seconds': totalDurationSeconds,
    'generated_at': generatedAt.toIso8601String(),
    'ttl_seconds': ttlSeconds,
  };
}
