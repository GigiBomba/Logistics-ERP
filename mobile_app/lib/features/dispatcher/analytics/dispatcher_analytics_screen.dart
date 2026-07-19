import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_state.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import 'analytics_providers.dart';

/// Condensed analytics screen for the dispatcher role.
///
/// Displays key business metrics across several sections:
/// - Overview (revenue, costs, profit)
/// - Financial summary with trends
/// - Fleet utilization
/// - Top clients by revenue
/// - Driver performance
///
/// Supports pull-to-refresh and a period toggle (this month / last month).
/// Each section independently handles loading, error, and empty states.
class DispatcherAnalyticsScreen extends ConsumerStatefulWidget {
  const DispatcherAnalyticsScreen({super.key});

  @override
  ConsumerState<DispatcherAnalyticsScreen> createState() =>
      _DispatcherAnalyticsScreenState();
}

class _DispatcherAnalyticsScreenState
    extends ConsumerState<DispatcherAnalyticsScreen> {
  AnalyticsPeriod _period = AnalyticsPeriod.thisMonth;

  /// Invalidates all analytics providers to trigger a full refresh.
  Future<void> _refresh() async {
    ref.invalidate(analyticsOverviewProvider(_period));
    ref.invalidate(analyticsFinancialProvider(_period));
    ref.invalidate(analyticsFleetUtilizationProvider(_period));
    ref.invalidate(analyticsTopClientsProvider(_period));
    ref.invalidate(analyticsDriverPerformanceProvider(_period));
    // Wait briefly for the first provider to settle for UX.
    await Future.delayed(const Duration(milliseconds: 300));
  }

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final theme = Theme.of(context);

    // Watch all analytics data providers.
    final overviewAsync = ref.watch(analyticsOverviewProvider(_period));
    final financialAsync = ref.watch(analyticsFinancialProvider(_period));
    final fleetAsync = ref.watch(analyticsFleetUtilizationProvider(_period));
    final clientsAsync = ref.watch(analyticsTopClientsProvider(_period));
    final driversAsync = ref.watch(analyticsDriverPerformanceProvider(_period));

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.nav_analytics),
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          children: [
            // ── Period Toggle ────────────────────────
            _PeriodToggle(
              period: _period,
              onChanged: (p) => setState(() => _period = p),
            ),
            const SizedBox(height: AppSpacing.lg),

            // ── Overview Card ────────────────────────
            overviewAsync.when(
              data: (data) => _OverviewCard(data: data),
              loading: () => const _ShimmerSection(
                height: 120,
                lineCount: 3,
              ),
              error: (e, _) => _SectionError(
                message: '$e',
                onRetry: () =>
                    ref.invalidate(analyticsOverviewProvider(_period)),
              ),
            ),
            const SizedBox(height: AppSpacing.md),

            // ── Financial Summary ────────────────────
            financialAsync.when(
              data: (data) => _FinancialSummaryCard(data: data),
              loading: () => const _ShimmerSection(
                height: 140,
                lineCount: 4,
              ),
              error: (e, _) => _SectionError(
                message: '$e',
                onRetry: () =>
                    ref.invalidate(analyticsFinancialProvider(_period)),
              ),
            ),
            const SizedBox(height: AppSpacing.md),

            // ── Fleet Utilization ────────────────────
            fleetAsync.when(
              data: (data) => _FleetUtilizationCard(data: data),
              loading: () => const _ShimmerSection(
                height: 100,
                lineCount: 3,
              ),
              error: (e, _) => _SectionError(
                message: '$e',
                onRetry: () =>
                    ref.invalidate(analyticsFleetUtilizationProvider(_period)),
              ),
            ),
            const SizedBox(height: AppSpacing.md),

            // ── Top Clients ──────────────────────────
            clientsAsync.when(
              data: (data) => _TopClientsCard(clients: data),
              loading: () => const _ShimmerSection(
                height: 140,
                lineCount: 4,
              ),
              error: (e, _) => _SectionError(
                message: '$e',
                onRetry: () =>
                    ref.invalidate(analyticsTopClientsProvider(_period)),
              ),
            ),
            const SizedBox(height: AppSpacing.md),

            // ── Driver Performance ───────────────────
            driversAsync.when(
              data: (data) => _DriverPerformanceCard(drivers: data),
              loading: () => const _ShimmerSection(
                height: 140,
                lineCount: 4,
              ),
              error: (e, _) => _SectionError(
                message: '$e',
                onRetry: () =>
                    ref.invalidate(analyticsDriverPerformanceProvider(_period)),
              ),
            ),
            const SizedBox(height: AppSpacing.xxl),

            // ── Open in Desktop CTA ──────────────────
            _DesktopCta(),
            const SizedBox(height: AppSpacing.lg),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Period Toggle
// ---------------------------------------------------------------------------

/// A segmented toggle to switch between "This Month" and "Last Month".
class _PeriodToggle extends StatelessWidget {
  const _PeriodToggle({
    required this.period,
    required this.onChanged,
  });

  final AnalyticsPeriod period;
  final ValueChanged<AnalyticsPeriod> onChanged;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    return SizedBox(
      width: double.infinity,
      child: SegmentedButton<AnalyticsPeriod>(
        segments: [
          ButtonSegment(
            value: AnalyticsPeriod.thisMonth,
            label: Text(loc.analytics_thisMonth),
          ),
          ButtonSegment(
            value: AnalyticsPeriod.lastMonth,
            label: Text(loc.analytics_lastMonth),
          ),
        ],
        selected: {period},
        onSelectionChanged: (set) => onChanged(set.first),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Overview Card
// ---------------------------------------------------------------------------

/// Displays total revenue, costs, and profit from the analytics overview.
class _OverviewCard extends StatelessWidget {
  const _OverviewCard({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final revenue = _numValue(data['totalRevenue']);
    final costs = _numValue(data['totalCosts']);
    final profit = _numValue(data['profit']);
    final rawProfit = data['profit'] is num ? data['profit'] as num : 0;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            loc.dispatcher_overview,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                child: _StatTile(
                  label: loc.analytics_revenue,
                  value: revenue,
                  color: AppColors.success,
                ),
              ),
              Expanded(
                child: _StatTile(
                  label: loc.analytics_costs,
                  value: costs,
                  color: AppColors.error,
                ),
              ),
              Expanded(
                child: _StatTile(
                  label: loc.analytics_profit,
                  value: profit,
                  color: rawProfit >= 0 ? AppColors.accent : AppColors.error,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Financial Summary
// ---------------------------------------------------------------------------

/// Displays revenue, costs, and profit with trend arrows.
class _FinancialSummaryCard extends StatelessWidget {
  const _FinancialSummaryCard({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final theme = Theme.of(context);

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            loc.analytics_financialSummary,
            style: theme.textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          _FinancialBar(
            label: loc.analytics_revenue,
            value: _numValue(data['revenue']),
            trend: _numValue(data['revenueTrend']),
            color: AppColors.success,
          ),
          const SizedBox(height: AppSpacing.sm),
          _FinancialBar(
            label: loc.analytics_costs,
            value: _numValue(data['costs']),
            trend: _numValue(data['costsTrend']),
            color: AppColors.error,
          ),
          const SizedBox(height: AppSpacing.sm),
          _FinancialBar(
            label: loc.analytics_profit,
            value: _numValue(data['profit']),
            trend: _numValue(data['profitTrend']),
            color: AppColors.accent,
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Fleet Utilization
// ---------------------------------------------------------------------------

/// Displays the percentage of active trucks and a count badge.
class _FleetUtilizationCard extends StatelessWidget {
  const _FleetUtilizationCard({required this.data});

  final Map<String, dynamic> data;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final theme = Theme.of(context);

    final active = _intValue(data['activeTrucks']);
    final total = _intValue(data['totalTrucks']);
    final percent = _doubleValue(data['utilizationPercent']);
    final fraction = total > 0 ? percent / 100.0 : 0.0;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                loc.analytics_fleetUtilization,
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.sm,
                  vertical: AppSpacing.xs,
                ),
                decoration: BoxDecoration(
                  color: AppColors.accentSubtle,
                  borderRadius: BorderRadius.circular(AppRadius.pill),
                ),
                child: Text(
                  loc.analytics_trucksActive
                      .replaceAll('{active}', '$active')
                      .replaceAll('{total}', '$total'),
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: AppColors.accent,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          // Progress bar.
          ClipRRect(
            borderRadius: BorderRadius.circular(AppRadius.pill),
            child: LinearProgressIndicator(
              value: fraction,
              minHeight: 10,
              backgroundColor: theme.colorScheme.surfaceContainerHighest,
              valueColor: AlwaysStoppedAnimation<Color>(
                percent >= 75
                    ? AppColors.success
                    : percent >= 50
                        ? AppColors.warning
                        : AppColors.error,
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            '${percent.toStringAsFixed(0)}%',
            style: theme.textTheme.bodySmall?.copyWith(
              fontWeight: FontWeight.w600,
              color: AppColors.textSecondaryLight,
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Top Clients
// ---------------------------------------------------------------------------

/// Lists the top 3 clients by revenue.
class _TopClientsCard extends StatelessWidget {
  const _TopClientsCard({required this.clients});

  final List<Map<String, dynamic>> clients;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final theme = Theme.of(context);

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            loc.analytics_topClients,
            style: theme.textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          if (clients.isEmpty)
            _EmptySection(
              icon: LucideIcons.users,
              message: loc.analytics_noData,
            )
          else
            ...clients.asMap().entries.map(
                  (entry) => Padding(
                    padding: EdgeInsets.only(
                      bottom: entry.key < clients.length - 1
                          ? AppSpacing.sm
                          : 0,
                    ),
                    child: _ClientRow(
                      rank: entry.key + 1,
                      name: '${entry.value['clientName'] ?? ''}',
                      revenue: _numValue(entry.value['revenue']),
                    ),
                  ),
                ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Driver Performance
// ---------------------------------------------------------------------------

/// Lists the top 3 drivers by trips and profit.
class _DriverPerformanceCard extends StatelessWidget {
  const _DriverPerformanceCard({required this.drivers});

  final List<Map<String, dynamic>> drivers;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final theme = Theme.of(context);

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            loc.analytics_driverPerformance,
            style: theme.textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          if (drivers.isEmpty)
            _EmptySection(
              icon: LucideIcons.users,
              message: loc.analytics_noData,
            )
          else
            ...drivers.asMap().entries.map(
                  (entry) => Padding(
                    padding: EdgeInsets.only(
                      bottom: entry.key < drivers.length - 1
                          ? AppSpacing.sm
                          : 0,
                    ),
                    child: _DriverRow(
                      rank: entry.key + 1,
                      name: '${entry.value['driverName'] ?? ''}',
                      trips: _intValue(entry.value['trips']),
                      profit: _numValue(entry.value['profit']),
                    ),
                  ),
                ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Open in Desktop CTA
// ---------------------------------------------------------------------------

/// A call-to-action card encouraging the user to open the full analytics on
/// desktop.
class _DesktopCta extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final theme = Theme.of(context);

    return AppCard(
      padding: const EdgeInsets.all(AppSpacing.lg),
      onTap: () {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Coming soon — full desktop analytics')),
        );
      },
      child: Row(
        children: [
          Icon(
            LucideIcons.monitor,
            size: 24,
            color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Text(
              loc.analytics_openDesktop,
              style: theme.textTheme.bodySmall?.copyWith(
                color: AppColors.textSecondaryLight,
              ),
            ),
          ),
          Icon(
            Icons.chevron_right,
            color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Shared Widgets
// ---------------------------------------------------------------------------

/// A single stat tile used in the overview card.
class _StatTile extends StatelessWidget {
  const _StatTile({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      children: [
        Text(
          label,
          style: theme.textTheme.bodySmall?.copyWith(
            color: AppColors.textSecondaryLight,
            fontSize: 11,
          ),
        ),
        const SizedBox(height: AppSpacing.xs),
        Text(
          value,
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w700,
            color: color,
          ),
        ),
      ],
    );
  }
}

/// A horizontal financial bar with label, value, and trend arrow.
class _FinancialBar extends StatelessWidget {
  const _FinancialBar({
    required this.label,
    required this.value,
    required this.trend,
    required this.color,
  });

  final String label;
  final String value;
  final String trend;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final trendNum = double.tryParse(trend) ?? 0;
    final isUp = trendNum > 0;
    final isFlat = trendNum == 0;

    return Row(
      children: [
        SizedBox(
          width: 64,
          child: Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
        const Spacer(),
        Text(
          value,
          style: const TextStyle(
            fontWeight: FontWeight.w600,
            fontSize: 13,
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        Icon(
          isFlat
              ? Icons.remove
              : isUp
                  ? Icons.arrow_upward
                  : Icons.arrow_downward,
          size: 16,
          color: isFlat
              ? AppColors.textSecondaryLight
              : isUp
                  ? AppColors.success
                  : AppColors.error,
        ),
        if (!isFlat)
          Text(
            '${trendNum.abs().toStringAsFixed(0)}%',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: isUp ? AppColors.success : AppColors.error,
            ),
          ),
      ],
    );
  }
}

/// A single row in the top clients list.
class _ClientRow extends StatelessWidget {
  const _ClientRow({
    required this.rank,
    required this.name,
    required this.revenue,
  });

  final int rank;
  final String name;
  final String revenue;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 22,
          height: 22,
          decoration: BoxDecoration(
            color: AppColors.accentSubtle,
            borderRadius: BorderRadius.circular(AppRadius.sm),
          ),
          child: Center(
            child: Text(
              '$rank',
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: AppColors.accent,
              ),
            ),
          ),
        ),
        const SizedBox(width: AppSpacing.md),
        Expanded(child: Text(name, style: const TextStyle(fontSize: 13))),
        Text(
          revenue,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

/// A single row in the driver performance list.
class _DriverRow extends StatelessWidget {
  const _DriverRow({
    required this.rank,
    required this.name,
    required this.trips,
    required this.profit,
  });

  final int rank;
  final String name;
  final int trips;
  final String profit;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 22,
          height: 22,
          decoration: BoxDecoration(
            color: AppColors.accentSubtle,
            borderRadius: BorderRadius.circular(AppRadius.sm),
          ),
          child: Center(
            child: Text(
              '$rank',
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: AppColors.accent,
              ),
            ),
          ),
        ),
        const SizedBox(width: AppSpacing.md),
        Expanded(child: Text(name, style: const TextStyle(fontSize: 13))),
        const SizedBox(width: AppSpacing.sm),
        Icon(
          LucideIcons.route,
          size: 14,
          color: AppColors.textSecondaryLight,
        ),
        const SizedBox(width: 2),
        Text(
          '$trips',
          style: const TextStyle(fontSize: 12),
        ),
        const SizedBox(width: AppSpacing.sm),
        Text(
          profit,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

/// An empty section placeholder within a card.
class _EmptySection extends StatelessWidget {
  const _EmptySection({
    required this.icon,
    required this.message,
  });

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
      child: EmptyState(
        icon: Icon(icon),
        title: message,
      ),
    );
  }
}

/// Error state for an individual section with a retry button.
class _SectionError extends StatelessWidget {
  const _SectionError({
    required this.message,
    required this.onRetry,
  });

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AppCard(
      child: Column(
        children: [
          Icon(
            LucideIcons.alertCircle,
            size: 32,
            color: AppColors.error.withValues(alpha: 0.6),
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            message,
            style: theme.textTheme.bodySmall?.copyWith(
              color: AppColors.textSecondaryLight,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.sm),
          TextButton.icon(
            onPressed: onRetry,
            icon: const Icon(LucideIcons.refreshCcw, size: 16),
            label: Text(context.loc.general_retry),
          ),
        ],
      ),
    );
  }
}

/// Shimmer loading placeholder for a section card.
class _ShimmerSection extends StatelessWidget {
  const _ShimmerSection({
    required this.height,
    required this.lineCount,
  });

  final double height;
  final int lineCount;

  @override
  Widget build(BuildContext context) {
    const widths = [0.4, 0.9, 0.6, 0.7];
    return SizedBox(
      height: height,
      child: ShimmerLoader(
        child: Card(
          margin: EdgeInsets.zero,
          child: Padding(
            padding: EdgeInsets.all(AppSpacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: List.generate(lineCount, (i) {
                return Padding(
                  padding: EdgeInsets.only(top: i == 0 ? 0 : AppSpacing.sm),
                  child: _ShimmerLine(width: widths[i % widths.length]),
                );
              }),
            ),
          ),
        ),
      ),
    );
  }
}

/// A single shimmer line placeholder.
class _ShimmerLine extends StatelessWidget {
  const _ShimmerLine({this.width = 1.0});

  final double width;

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      widthFactor: width,
      child: Container(
        height: 12,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(4),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

String _numValue(dynamic value) {
  if (value == null) return '—';
  final num v = value is num ? value : (double.tryParse('$value') ?? 0);
  if (v == 0) return '—';
  if (v >= 1e12) return '~1T';
  if (v >= 1e9) return '~1B';
  if (v >= 1e6) return '~1M';
  return v.toStringAsFixed(2);
}

int _intValue(dynamic value) {
  if (value == null) return 0;
  if (value is int) return value;
  if (value is double) return value.round();
  return int.tryParse('$value') ?? 0;
}

double _doubleValue(dynamic value) {
  if (value == null) return 0.0;
  if (value is double) return value;
  if (value is int) return value.toDouble();
  return double.tryParse('$value') ?? 0.0;
}
