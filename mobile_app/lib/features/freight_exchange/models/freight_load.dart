/// A load listed on a freight exchange (provider-agnostic).
///
/// No TIMOCOM-specific field names — the mobile client only consumes the
/// provider-agnostic backend endpoint. The backend adapter maps provider
/// fields to this shape.
class FreightLoad {
  final String id;
  final String origin;
  final String destination;
  final String? cargoType;
  final double? price;
  final String? currency;
  final DateTime? pickupDate;
  final DateTime? deadlineDate;
  final double? weightKg;
  final String? distanceKm;

  const FreightLoad({
    required this.id,
    required this.origin,
    required this.destination,
    this.cargoType,
    this.price,
    this.currency,
    this.pickupDate,
    this.deadlineDate,
    this.weightKg,
    this.distanceKm,
  });

  factory FreightLoad.fromJson(Map<String, dynamic> json) => FreightLoad(
        id: json['id'] as String? ?? '',
        origin: json['origin'] as String? ?? '',
        destination: json['destination'] as String? ?? '',
        cargoType: json['cargo_type'] as String?,
        price: (json['price'] as num?)?.toDouble(),
        currency: json['currency'] as String?,
        pickupDate: json['pickup_date'] != null
            ? DateTime.tryParse(json['pickup_date'] as String)
            : null,
        deadlineDate: json['deadline_date'] != null
            ? DateTime.tryParse(json['deadline_date'] as String)
            : null,
        weightKg: (json['weight_kg'] as num?)?.toDouble(),
        distanceKm: json['distance_km'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'origin': origin,
        'destination': destination,
        'cargo_type': cargoType,
        'price': price,
        'currency': currency,
        'pickup_date': pickupDate?.toIso8601String(),
        'deadline_date': deadlineDate?.toIso8601String(),
        'weight_kg': weightKg,
        'distance_km': distanceKm,
      };
}
