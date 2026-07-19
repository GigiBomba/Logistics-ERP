import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/features/teams/screens/teams_screen.dart';

void main() {
  group('Teams Filter', () {
    test('DriverFilter enum has 4 values', () {
      expect(DriverFilter.values.length, 4);
      expect(DriverFilter.values, contains(DriverFilter.all));
      expect(DriverFilter.values, contains(DriverFilter.available));
      expect(DriverFilter.values, contains(DriverFilter.driving));
      expect(DriverFilter.values, contains(DriverFilter.off));
    });
  });
}
