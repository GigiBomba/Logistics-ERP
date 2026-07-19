import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/models/driver.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_state.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import '../../../shared/widgets/status_badge.dart';
import '../../dispatcher/home/dispatcher_providers.dart';

/// Driver status filter options.
enum DriverFilter { all, available, driving, off }

/// Teams screen — drivers/roster view with filter chips.
///
/// Shows a list of all company drivers with status filtering.
/// Each driver shows avatar, name, status indicator, and current assignment.
class TeamsScreen extends ConsumerStatefulWidget {
  const TeamsScreen({super.key});

  @override
  ConsumerState<TeamsScreen> createState() => _TeamsScreenState();
}

class _TeamsScreenState extends ConsumerState<TeamsScreen> {
  DriverFilter _selectedFilter = DriverFilter.all;

  @override
  Widget build(BuildContext context) {
    // Placeholder: in production this fetches from GET /drivers
    // For now, show a structured scaffold with filter chips
    final loc = context.loc;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.nav_teams)),
      body: Column(
        children: [
          // Filter chips
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: DriverFilter.values.map((filter) {
                  final selected = _selectedFilter == filter;
                  return Padding(
                    padding: const EdgeInsets.only(right: AppSpacing.sm),
                    child: FilterChip(
                      label: Text(_filterLabel(filter, loc)),
                      selected: selected,
                      onSelected: (_) {
                        setState(() => _selectedFilter = filter);
                      },
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
          // Driver list
          Expanded(
            child: ref.watch(dispatcherDriversProvider).when(
              loading: () => ListView.builder(
                itemCount: 6,
                itemBuilder: (_, __) => const ShimmerCard(),
              ),
              error: (e, _) => Center(
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: Text(
                    '${loc.general_error}: $e',
                    style: theme.textTheme.bodyMedium,
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
              data: (drivers) {
                final filtered = _selectedFilter == DriverFilter.all
                    ? drivers
                    : drivers.where((d) {
                        final status = d['status'] as String? ?? '';
                        return status == _filterToStatus(_selectedFilter);
                      }).toList();
                if (filtered.isEmpty) {
                  return Center(
                    child: EmptyState(
                      icon: const Icon(LucideIcons.users, size: 56),
                      title: loc.nav_teams,
                      subtitle: loc.teams_placeholder,
                    ),
                  );
                }
                return ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                  itemCount: filtered.length,
                  itemBuilder: (context, index) {
                    final d = filtered[index];
                    return Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                      child: AppCard(
                        child: Row(
                          children: [
                            CircleAvatar(
                              backgroundColor: AppColors.primary.withValues(alpha: 0.15),
                              child: Text(
                                (d['fullName'] as String? ?? '?')[0].toUpperCase(),
                                style: TextStyle(
                                  color: AppColors.primary,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            const SizedBox(width: AppSpacing.md),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    d['fullName'] as String? ?? '',
                                    style: theme.textTheme.titleSmall,
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    d['phone'] as String? ?? '',
                                    style: theme.textTheme.bodySmall?.copyWith(
                                      color: AppColors.textSecondary,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            StatusBadge(statusKey: d['status'] as String? ?? ''),
                          ],
                        ),
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  String _filterLabel(DriverFilter filter, AppLocalizations loc) {
    switch (filter) {
      case DriverFilter.all:
        return loc.teams_filterAll;
      case DriverFilter.available:
        return loc.teams_filterAvailable;
      case DriverFilter.driving:
        return loc.teams_filterDriving;
      case DriverFilter.off:
        return loc.teams_filterOff;
    }
  }

  String _filterToStatus(DriverFilter filter) {
    switch (filter) {
      case DriverFilter.available:
        return 'available';
      case DriverFilter.driving:
        return 'driving';
      case DriverFilter.off:
        return 'off';
      case DriverFilter.all:
        return '';
    }
  }
}
