/// Status values for a driver's assigned transport trip.
enum TripStatus { planned, loading, inTransit, delivered, cancelled }

/// Confidence level of the ETA value returned by the server.
enum EtaConfidence { live, stale, unavailable }

/// Server-provided overview of the driver's currently assigned trip.
///
/// All fields except [etaConfidence] are nullable — when no transport is
/// assigned, the endpoint returns HTTP 200 with all data fields null
/// (not 404), and the client renders the empty state.
class DriverTripOverview {
  final String? transportId;
  final String? loadInfo;
  final String? origin;
  final String? destination;
  final TripStatus? status;
  final DateTime? statusSince;
  final DateTime? eta;
  final EtaConfidence etaConfidence;

  const DriverTripOverview({
    this.transportId,
    this.loadInfo,
    this.origin,
    this.destination,
    this.status,
    this.statusSince,
    this.eta,
    required this.etaConfidence,
  });

  /// Elapsed time since [statusSince], or null if unknown.
  Duration? get elapsed =>
      statusSince == null ? null : DateTime.now().difference(statusSince!);

  /// Creates from a JSON map (camelCase keys from the Dart convention or
  /// snake_case from the backend).
  factory DriverTripOverview.fromJson(Map<String, dynamic> json) {
    TripStatus? _parseStatus(String? s) => switch (s) {
      'planned' => TripStatus.planned,
      'loading' => TripStatus.loading,
      'in_transit' || 'inTransit' => TripStatus.inTransit,
      'delivered' => TripStatus.delivered,
      'cancelled' => TripStatus.cancelled,
      _ => null,
    };

    EtaConfidence _parseConfidence(String? s) => switch (s) {
      'live' => EtaConfidence.live,
      'stale' => EtaConfidence.stale,
      _ => EtaConfidence.unavailable,
    };

    return DriverTripOverview(
      transportId: json['transport_id'] as String?,
      loadInfo: json['load_info'] as String?,
      origin: json['origin'] as String?,
      destination: json['destination'] as String?,
      status: _parseStatus(json['status'] as String?),
      statusSince: json['status_since'] != null
          ? DateTime.tryParse(json['status_since'] as String)
          : null,
      eta: json['eta'] != null
          ? DateTime.tryParse(json['eta'] as String)
          : null,
      etaConfidence: _parseConfidence(json['eta_confidence'] as String?),
    );
  }

  Map<String, dynamic> toJson() => {
    'transport_id': transportId,
    'load_info': loadInfo,
    'origin': origin,
    'destination': destination,
    'status': status?.name,
    'status_since': statusSince?.toIso8601String(),
    'eta': eta?.toIso8601String(),
    'eta_confidence': etaConfidence.name,
  };
}
