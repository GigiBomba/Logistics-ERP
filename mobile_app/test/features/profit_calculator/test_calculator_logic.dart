import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/features/profit_calculator/models/calculator_logic.dart';

void main() {
  group('ProfitCalculation', () {
    test('positive profit', () {
      final calc = ProfitCalculation(
        revenue: 10000,
        fuelCost: 2000,
        tollCost: 500,
        maintenanceAmortization: 300,
        driverCost: 1500,
      );
      expect(calc.totalCosts, 4300);
      expect(calc.profit, 5700);
      expect(calc.profitMargin, closeTo(57.0, 0.01));
    });

    test('break-even', () {
      final calc = ProfitCalculation(
        revenue: 5000,
        fuelCost: 2000,
        tollCost: 1000,
        maintenanceAmortization: 500,
        driverCost: 1500,
      );
      expect(calc.totalCosts, 5000);
      expect(calc.profit, 0);
      expect(calc.profitMargin, 0);
    });

    test('negative profit (loss)', () {
      final calc = ProfitCalculation(
        revenue: 3000,
        fuelCost: 2000,
        tollCost: 1000,
        maintenanceAmortization: 500,
        driverCost: 1500,
      );
      expect(calc.totalCosts, 5000);
      expect(calc.profit, -2000);
      expect(calc.profitMargin, closeTo(-66.67, 0.01));
    });

    test('formatProfit', () {
      final calc = ProfitCalculation(
        revenue: 10000,
        fuelCost: 2000,
        tollCost: 500,
        maintenanceAmortization: 300,
        driverCost: 1500,
      );
      expect(calc.formatProfit('\$'), '\$5700.00');
      expect(calc.formatProfit('€'), '€5700.00');
    });

    test('zero revenue has zero profit margin', () {
      final calc = ProfitCalculation(
        revenue: 0,
        fuelCost: 100,
        tollCost: 50,
        maintenanceAmortization: 20,
        driverCost: 30,
      );
      expect(calc.totalCosts, 200);
      expect(calc.profit, -200);
      expect(calc.profitMargin, 0);
    });
  });
}
