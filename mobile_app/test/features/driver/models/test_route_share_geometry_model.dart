import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/features/driver/models/route_share_geometry.dart';

void main() {
  group('RoutePoint', () {
    test('fromJson parses correctly', () {
      final json = {'lat': 44.4268, 'lng': 26.1025};
      final point = RoutePoint.fromJson(json);
      expect(point.lat, 44.4268);
      expect(point.lng, 26.1025);
    });

    test('toJson round-trips correctly', () {
      final original = const RoutePoint(lat: 45.9432, lng: 24.9668);
      final json = original.toJson();
      final restored = RoutePoint.fromJson(json);
      expect(restored.lat, original.lat);
      expect(restored.lng, original.lng);
    });
  });

  group('RouteInstruction', () {
    test('fromJson parses correctly', () {
      final json = {
        'text_key': 'turn_left',
        'distance_meters': 150.0,
        'point_index': 3,
      };
      final instruction = RouteInstruction.fromJson(json);
      expect(instruction.textKey, 'turn_left');
      expect(instruction.distanceMeters, 150.0);
      expect(instruction.pointIndex, 3);
    });

    test('fromJson uses defaults for missing fields', () {
      final json = <String, dynamic>{};
      final instruction = RouteInstruction.fromJson(json);
      expect(instruction.textKey, '');
      expect(instruction.distanceMeters, 0);
      expect(instruction.pointIndex, 0);
    });

    test('toJson round-trips correctly', () {
      final original = const RouteInstruction(
        textKey: 'straight',
        distanceMeters: 500.0,
        pointIndex: 1,
      );
      final json = original.toJson();
      final restored = RouteInstruction.fromJson(json);
      expect(restored.textKey, original.textKey);
      expect(restored.distanceMeters, original.distanceMeters);
      expect(restored.pointIndex, original.pointIndex);
    });
  });

  group('RouteShareGeometry', () {
    test('fromJson parses all fields correctly', () {
      final json = {
        'transport_id': 'T-456',
        'points': [
          {'lat': 44.4268, 'lng': 26.1025},
          {'lat': 44.4390, 'lng': 26.0978},
        ],
        'instructions': [
          {
            'text_key': 'start',
            'distance_meters': 0.0,
            'point_index': 0,
          },
          {
            'text_key': 'turn_right',
            'distance_meters': 200.0,
            'point_index': 1,
          },
        ],
        'total_distance_meters': 12500.0,
        'total_duration_seconds': 900,
        'generated_at': '2026-07-19T10:00:00Z',
        'ttl_seconds': 300,
      };

      final geometry = RouteShareGeometry.fromJson(json);
      expect(geometry.transportId, 'T-456');
      expect(geometry.points.length, 2);
      expect(geometry.points[0].lat, 44.4268);
      expect(geometry.instructions.length, 2);
      expect(geometry.instructions[1].textKey, 'turn_right');
      expect(geometry.totalDistanceMeters, 12500.0);
      expect(geometry.totalDurationSeconds, 900);
      expect(geometry.ttlSeconds, 300);
    });

    test('fromJson handles empty points and instructions', () {
      final json = {
        'transport_id': 'T-789',
        'points': [],
        'instructions': [],
        'total_distance_meters': 0,
        'total_duration_seconds': 0,
        'generated_at': '2026-07-19T10:00:00Z',
        'ttl_seconds': 300,
      };

      final geometry = RouteShareGeometry.fromJson(json);
      expect(geometry.points, isEmpty);
      expect(geometry.instructions, isEmpty);
    });

    test('isStale returns false for fresh data', () {
      final geometry = RouteShareGeometry(
        transportId: 'T-001',
        points: const [],
        totalDistanceMeters: 0,
        totalDurationSeconds: 0,
        generatedAt: DateTime.now().subtract(const Duration(seconds: 10)),
        ttlSeconds: 300,
      );
      expect(geometry.isStale, isFalse);
    });

    test('isStale returns true for expired data', () {
      final geometry = RouteShareGeometry(
        transportId: 'T-001',
        points: const [],
        totalDistanceMeters: 0,
        totalDurationSeconds: 0,
        generatedAt: DateTime.now().subtract(const Duration(seconds: 400)),
        ttlSeconds: 300,
      );
      expect(geometry.isStale, isTrue);
    });

    test('toJson round-trips correctly', () {
      final original = RouteShareGeometry(
        transportId: 'T-999',
        points: const [
          RoutePoint(lat: 44.0, lng: 26.0),
          RoutePoint(lat: 45.0, lng: 27.0),
        ],
        instructions: const [
          RouteInstruction(textKey: 'go', distanceMeters: 100, pointIndex: 0),
        ],
        totalDistanceMeters: 5000.0,
        totalDurationSeconds: 360,
        generatedAt: DateTime(2026, 7, 19, 10, 0, 0),
        ttlSeconds: 600,
      );

      final json = original.toJson();
      final restored = RouteShareGeometry.fromJson(json);

      expect(restored.transportId, original.transportId);
      expect(restored.points.length, original.points.length);
      expect(restored.points[0].lat, original.points[0].lat);
      expect(restored.instructions.length, original.instructions.length);
      expect(restored.instructions[0].textKey, original.instructions[0].textKey);
      expect(restored.totalDistanceMeters, original.totalDistanceMeters);
      expect(restored.totalDurationSeconds, original.totalDurationSeconds);
      expect(restored.ttlSeconds, original.ttlSeconds);
    });
  });
}
