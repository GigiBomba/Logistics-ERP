import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_state.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import '../home/dispatcher_providers.dart';

/// Status filter options for the driver list.
enum _DriverFilter {
  /// Show all drivers regardless of status.
  all,

  /// Show only drivers with status "available".
  available,

  /// Show only drivers with status "driving".
  driving,

  /// Show only drivers with status "off".
  off,
}

/// Screen that displays a searchable/filterable list of all drivers.
///
/// Dispatchers can view each driver's current status, assigned transport,
/// and vehicle. Tapping a driver card navigates to a detail view (to be
/// implemented).
///
/// Features:
/// - Filter chips: All, Available, Driving, Off
/// - Each driver shows avatar, name, status indicator, transport & vehicle info
/// - Pull-to-refresh
/// - Loading / error / empty states
class DriverListScreen extends ConsumerStatefulWidget {
  const DriverListScreen({super.key});

  @override
  ConsumerState<DriverListScreen> createState() => _DriverListScreenState();
}

class _DriverListScreenState extends ConsumerState<DriverListScreen> {
  _DriverFilter _selectedFilter = _DriverFilter.all;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final driversAsync = ref.watch(dispatcherDriversProvider);

    return Scaffold(
      appBar: AppBar(title: Text(loc.nav_drivers)),
      body: Column(
        children: [
        // ── Filter chips ──────────────────────────
        _buildFilterChips(loc),

        // ── Content ────────────────────────────────
        Expanded(
          child: driversAsync.when(
            loading: () => const _DriverListShimmer(),
            error: (err, stack) => _ErrorRetry(
              message: err.toString(),
              onRetry: () =>
                  ref.invalidate(dispatcherDriversProvider),
            ),
            data: (drivers) {
              final filtered = _filterDrivers(drivers);
              if (filtered.isEmpty) {
                return const _EmptyDrivers();
              }
              return _DriverListView(
                drivers: filtered,
                onRefresh: () async =>
                    ref.invalidate(dispatcherDriversProvider),
              );
            },
          ),
        ),
        ],
      ),
    );
  }

  /// Builds the horizontal filter chip row.
  Widget _buildFilterChips(AppLocalizations loc) {
    const filters = _DriverFilter.values;
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.sm,
      ),
      child: Row(
        children: filters.map((filter) {
          final isSelected = filter == _selectedFilter;
          return Padding(
            padding: const EdgeInsets.only(right: AppSpacing.sm),
            child: FilterChip(
              label: Text(_filterLabel(filter, loc)),
              selected: isSelected,
              onSelected: (_) =>
                  setState(() => _selectedFilter = filter),
            ),
          );
        }).toList(),
      ),
    );
  }

  /// Returns the translated label for a given filter.
  String _filterLabel(_DriverFilter filter, AppLocalizations loc) {
    return switch (filter) {
      _DriverFilter.all => loc.nav_drivers,
      _DriverFilter.available => loc.dispatcher_activeDrivers,
      _DriverFilter.driving => 'Driving',
      _DriverFilter.off => 'Off',
    };
  }

  /// Maps display filters to actual API status values.
  static const _statusFilterMap = {
    _DriverFilter.available: ['available'],
    _DriverFilter.driving: ['driving'],
    _DriverFilter.off: ['offline', 'off_duty', 'inactive'],
  };

  /// Filters the driver list based on [_selectedFilter].
  List<Map<String, dynamic>> _filterDrivers(
    List<Map<String, dynamic>> drivers,
  ) {
    if (_selectedFilter == _DriverFilter.all) return drivers;
    final statuses = _statusFilterMap[_selectedFilter] ?? [];
    return drivers
        .where((d) => statuses.contains(d['status'] as String?))
        .toList();
  }
}

/// Shimmer loading state for the driver list.
class _DriverListShimmer extends StatelessWidget {
  const _DriverListShimmer();

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.all(AppSpacing.lg),
      itemCount: 6,
      separatorBuilder: (_, __) =>
          const SizedBox(height: AppSpacing.sm),
      itemBuilder: (_, __) => const ShimmerCard(),
    );
  }
}

/// Error state with retry button.
class _ErrorRetry extends StatelessWidget {
  const _ErrorRetry({
    required this.message,
    required this.onRetry,
  });

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.error_outline,
              size: 48,
              color: AppColors.error,
            ),
            const SizedBox(height: AppSpacing.md),
            Text(
              loc.general_error,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              message,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                color: AppColors.neutralText,
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: Text(loc.general_retry),
            ),
          ],
        ),
      ),
    );
  }
}

/// Empty state when no drivers match the current filter.
class _EmptyDrivers extends StatelessWidget {
  const _EmptyDrivers();

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    return EmptyState(
      icon: const Icon(Icons.person_outline),
      title: loc.nav_drivers,
      subtitle: loc.driver_noTransports,
    );
  }
}

/// Scrollable list of driver cards with pull-to-refresh.
class _DriverListView extends StatelessWidget {
  const _DriverListView({
    required this.drivers,
    required this.onRefresh,
  });

  final List<Map<String, dynamic>> drivers;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: onRefresh,
      child: ListView.separated(
        padding: const EdgeInsets.all(AppSpacing.lg),
        itemCount: drivers.length,
        separatorBuilder: (_, __) =>
            const SizedBox(height: AppSpacing.sm),
        itemBuilder: (context, index) =>
            _DriverCard(driver: drivers[index]),
      ),
    );
  }
}

/// A single driver card displaying avatar, name, status, transport, and
/// vehicle information.
class _DriverCard extends StatelessWidget {
  const _DriverCard({required this.driver});

  final Map<String, dynamic> driver;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final name = driver['name'] as String? ?? '';
    final status = driver['status'] as String? ?? 'off';
    final currentTransport =
        driver['current_transport'] as Map<String, dynamic>?;
    final currentVehicle = driver['current_vehicle'] as String?;

    return AppCard(
      onTap: () {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('${loc.nav_drivers}: $name'),
          ),
        );
      },
      child: Row(
        children: [
          // ── Avatar ──────────────────────────────
          CircleAvatar(
            backgroundColor:
                AppColors.accent.withValues(alpha: 0.15),
            child: Text(
              name.isNotEmpty ? name[0].toUpperCase() : '?',
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                color: AppColors.accent,
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.md),

          // ── Name & details ──────────────────────
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  name,
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 15,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                _StatusIndicator(status: status),
                if (currentTransport != null) ...[
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    currentTransport['name'] as String? ?? '',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppColors.neutralText,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
                if (currentVehicle != null &&
                    currentVehicle.isNotEmpty) ...[
                  const SizedBox(height: AppSpacing.xs),
                  Row(
                    children: [
                      Icon(
                        Icons.local_shipping_outlined,
                        size: 14,
                        color: AppColors.neutralText,
                      ),
                      const SizedBox(width: AppSpacing.xs),
                      Text(
                        currentVehicle,
                        style: TextStyle(
                          fontSize: 12,
                          color: AppColors.neutralText,
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),

          // ── Chevron ─────────────────────────────
          const Icon(
            Icons.chevron_right,
            color: AppColors.neutralText,
          ),
        ],
      ),
    );
  }
}

/// Colored dot + text for a driver's availability status.
class _StatusIndicator extends StatelessWidget {
  const _StatusIndicator({required this.status});

  final String status;

  @override
  Widget build(BuildContext context) {
    final (Color dotColor, String label) = switch (status) {
      'available' => (AppColors.success, 'Available'),
      'driving' => (AppColors.info, 'Driving'),
      _ => (AppColors.neutralText, 'Inactive'),
    };

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            color: dotColor,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: AppSpacing.xs),
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            color: dotColor,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}
