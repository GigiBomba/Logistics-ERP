import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/features/freight_exchange/models/freight_load.dart';

void main() {
  group('FreightLoad', () {
    test('round-trips from JSON with all fields', () {
      final json = {
        'id': '1',
        'provider_id': 'timocom',
        'provider_load_id': 'TL-001',
        'origin': 'Berlin',
        'destination': 'Paris',
        'cargo_type': 'curtain',
        'price': 1450.0,
        'currency': 'EUR',
        'pickup_date': '2026-09-15T08:00:00.000Z',
        'deadline_date': '2026-09-16T18:00:00.000Z',
        'weight_kg': 21000.0,
        'distance_km': '1050.5',
      };

      final load = FreightLoad.fromJson(json);
      expect(load.id, '1');
      expect(load.providerId, 'timocom');
      expect(load.providerLoadId, 'TL-001');
      expect(load.origin, 'Berlin');
      expect(load.destination, 'Paris');
      expect(load.cargoType, 'curtain');
      expect(load.price, 1450.0);
      expect(load.currency, 'EUR');
      expect(load.pickupDate, DateTime.parse('2026-09-15T08:00:00.000Z'));
      expect(load.deadlineDate, DateTime.parse('2026-09-16T18:00:00.000Z'));
      expect(load.weightKg, 21000.0);
      expect(load.distanceKm, '1050.5');

      final back = load.toJson();
      expect(back['id'], '1');
      expect(back['provider_id'], 'timocom');
      expect(back['provider_load_id'], 'TL-001');
      expect(back['origin'], 'Berlin');
      expect(back['distance_km'], '1050.5');
    });

    test('handles missing optional fields', () {
      final json = {
        'id': '2',
        'provider_id': 'trans_eu',
        'provider_load_id': 'TE-002',
        'origin': 'Bucharest',
        'destination': 'Cluj',
      };

      final load = FreightLoad.fromJson(json);
      expect(load.cargoType, isNull);
      expect(load.price, isNull);
      expect(load.pickupDate, isNull);
      expect(load.weightKg, isNull);
      expect(load.distanceKm, isNull);

      final back = load.toJson();
      expect(back.containsKey('cargo_type'), isTrue);
      expect(back['cargo_type'], isNull);
    });
  });
}
