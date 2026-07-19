/// Pure client-side profit calculator.
///
/// Revenue minus costs — no backend calls.
class ProfitCalculation {
  final double revenue;
  final double fuelCost;
  final double tollCost;
  final double maintenanceAmortization;
  final double driverCost;

  const ProfitCalculation({
    required this.revenue,
    required this.fuelCost,
    required this.tollCost,
    required this.maintenanceAmortization,
    required this.driverCost,
  });

  double get totalCosts =>
      fuelCost + tollCost + maintenanceAmortization + driverCost;

  double get profit => revenue - totalCosts;

  double get profitMargin =>
      revenue > 0 ? (profit / revenue) * 100 : 0.0;

  /// Returns profit formatted to 2 decimal places with currency symbol.
  String formatProfit(String currencySymbol) =>
      '$currencySymbol${profit.toStringAsFixed(2)}';
}
