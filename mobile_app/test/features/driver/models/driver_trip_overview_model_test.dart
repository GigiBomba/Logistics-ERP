import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/features/driver/models/driver_trip_overview.dart';

void main() {
  group('DriverTripOverview', () {
    test('fromJson parses all fields correctly', () {
      final json = {
        'transport_id': 'T-123',
        'load_info': 'Electronics shipment',
        'origin': 'Warehouse A',
        'destination': 'Store B',
        'status': 'in_transit',
        'status_since': '2026-07-19T08:00:00Z',
        'eta': '2026-07-19T14:00:00Z',
        'eta_confidence': 'live',
      };

      final model = DriverTripOverview.fromJson(json);
      expect(model.transportId, 'T-123');
      expect(model.loadInfo, 'Electronics shipment');
      expect(model.origin, 'Warehouse A');
      expect(model.destination, 'Store B');
      expect(model.status, TripStatus.inTransit);
      expect(model.etaConfidence, EtaConfidence.live);
      expect(model.elapsed, isNotNull);
    });

    test('fromJson handles null transport (empty state)', () {
      final json = {
        'transport_id': null,
        'load_info': null,
        'origin': null,
        'destination': null,
        'status': null,
        'status_since': null,
        'eta': null,
        'eta_confidence': 'unavailable',
      };

      final model = DriverTripOverview.fromJson(json);
      expect(model.transportId, isNull);
      expect(model.status, isNull);
      expect(model.etaConfidence, EtaConfidence.unavailable);
      expect(model.elapsed, isNull);
    });

    test('toJson round-trips correctly', () {
      final original = DriverTripOverview(
        transportId: 'T-123',
        loadInfo: 'Test load',
        origin: 'A',
        destination: 'B',
        status: TripStatus.loading,
        statusSince: DateTime(2026, 7, 19, 8),
        eta: DateTime(2026, 7, 19, 14),
        etaConfidence: EtaConfidence.stale,
      );

      final json = original.toJson();
      final restored = DriverTripOverview.fromJson(json);

      expect(restored.transportId, original.transportId);
      expect(restored.status, original.status);
      expect(restored.etaConfidence, original.etaConfidence);
    });
  });
}
