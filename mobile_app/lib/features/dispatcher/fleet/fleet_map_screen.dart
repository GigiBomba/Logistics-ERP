import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/models/fleet_position.dart';
import '../../../shared/widgets/offline_banner.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import '../../../shared/widgets/staleness_indicator.dart';
import '../home/dispatcher_providers.dart';

/// Full-screen live fleet map that shows vehicle positions with color-coded
/// markers, pull-to-refresh, offline awareness, and loading / error states.
class FleetMapScreen extends ConsumerWidget {
  const FleetMapScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOffline = ref.watch(isOfflineProvider);
    final fleetAsync = ref.watch(fleetPositionsProvider);
    final loc = context.loc;

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(fleetPositionsProvider);
        return ref.read(fleetPositionsProvider.future);
      },
      child: fleetAsync.when(
        loading: () => const _LoadingView(),
        error: (err, _) => _ErrorView(
          message: err.toString(),
          onRetry: () => ref.invalidate(fleetPositionsProvider),
        ),
        data: (positions) => _MapView(
          positions: positions,
          isOffline: isOffline,
        ),
      ),
    );
  }

  /// Returns the most recent [lastUpdate] across all positions, or `null`.
  DateTime? _computeLastUpdated(List<FleetPosition>? positions) {
    if (positions == null || positions.isEmpty) return null;
    return positions
        .map((p) => p.lastUpdate)
        .reduce((a, b) => a.isAfter(b) ? a : b);
  }
}

// ---------------------------------------------------------------------------
// Loading state — shimmer placeholder over the map area
// ---------------------------------------------------------------------------

class _LoadingView extends StatelessWidget {
  const _LoadingView();

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: SizedBox(
          height: constraints.maxHeight,
          child: const ShimmerLoader(child: _MapShimmer()),
        ),
      ),
    );
  }
}

class _MapShimmer extends StatelessWidget {
  const _MapShimmer();

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: Colors.grey[300],
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      child: Center(
        child: Icon(
          Icons.map,
          size: 64,
          color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.2),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Error state — message + retry button
// ---------------------------------------------------------------------------

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorView({
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    return LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: SizedBox(
          height: constraints.maxHeight,
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.xxl),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    LucideIcons.cloudOff,
                    size: 64,
                    color: AppColors.error,
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  Text(
                    loc.general_error,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    message,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context)
                          .colorScheme
                          .onSurface
                          .withValues(alpha: 0.6),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xl),
                  FilledButton.icon(
                    onPressed: onRetry,
                    icon: const Icon(LucideIcons.refreshCw, size: 18),
                    label: Text(loc.general_retry),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Data state — full-screen map with vehicle markers
// ---------------------------------------------------------------------------

class _MapView extends StatelessWidget {
  final List<FleetPosition> positions;
  final bool isOffline;

  const _MapView({
    required this.positions,
    required this.isOffline,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: FlutterMap(
            options: MapOptions(
              initialCenter: const LatLng(46.0, 25.0),
              initialZoom: 7.0,
            ),
            children: [
              TileLayer(
                urlTemplate:
                    'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.operion.mobile',
              ),
              MarkerLayer(markers: _buildMarkers(context)),
            ],
          ),
        ),
      ],
    );
  }

  List<Marker> _buildMarkers(BuildContext context) {
    // Filter out positions with invalid coordinates (0,0 sentinel)
    return positions
        .where((p) => p.latitude != 0.0 || p.longitude != 0.0)
        .map((p) => Marker(
              point: LatLng(p.latitude, p.longitude),
              width: 40,
              height: 40,
              child: GestureDetector(
                onTap: () => _showVehicleDetail(context, p),
                child: _VehicleMarker(status: p.status),
              ),
            ))
        .toList();
  }

  void _showVehicleDetail(BuildContext context, FleetPosition vehicle) {
    final loc = context.loc;
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.xl)),
      ),
      builder: (ctx) {
        final theme = Theme.of(ctx);
        return Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.xl,
            AppSpacing.sm,
            AppSpacing.xl,
            AppSpacing.xl,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Drag handle
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: AppSpacing.lg),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              // Vehicle plate + marker icon
              Row(
                children: [
                  _VehicleMarker(status: vehicle.status, size: 28),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Text(
                      vehicle.plate,
                      style: theme.textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.lg),
              // Driver name
              _DetailRow(
                icon: LucideIcons.user,
                label: vehicle.driverName.isNotEmpty
                    ? vehicle.driverName
                    : '-',
              ),
              const SizedBox(height: AppSpacing.sm),
              // Status
              _DetailRow(
                icon: LucideIcons.info,
                label: vehicle.status.isNotEmpty
                    ? _capitalize(vehicle.status)
                    : '-',
              ),
              const SizedBox(height: AppSpacing.sm),
              // Last update
              _DetailRow(
                icon: LucideIcons.clock,
                label:
                    '${loc.general_lastUpdated}: ${_formatElapsed(vehicle.lastUpdate, loc)}',
              ),
            ],
          ),
        );
      },
    );
  }

  /// Formats the elapsed time since [dt] using localised strings.
  String _formatElapsed(DateTime dt, AppLocalizations loc) {
    final diff = DateTime.now().difference(dt);
    if (diff.isNegative) return loc.general_justNow;
    if (diff.inMinutes < 1) return loc.general_justNow;
    if (diff.inMinutes < 60) {
      return loc.general_minAgo.replaceAll('{count}', '${diff.inMinutes}');
    }
    if (diff.inHours < 2) return loc.general_hourAgo;
    if (diff.inHours < 24) {
      return loc.general_hoursAgo.replaceAll('{count}', '${diff.inHours}');
    }
    return '${diff.inDays}d';
  }

  String _capitalize(String s) {
    if (s.isEmpty) return s;
    return '${s[0].toUpperCase()}${s.substring(1)}';
  }
}

// ---------------------------------------------------------------------------
// Vehicle marker — color-coded circle with truck icon
// ---------------------------------------------------------------------------

class _VehicleMarker extends StatelessWidget {
  final String status;
  final double size;

  const _VehicleMarker({
    required this.status,
    this.size = 32,
  });

  @override
  Widget build(BuildContext context) {
    final color = _colorForStatus(status);
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 2),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.3),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Icon(
        LucideIcons.truck,
        size: size * 0.5,
        color: Colors.white,
      ),
    );
  }

  /// Returns a status-appropriate color:
  ///   active/driving → green (success)
  ///   stopped        → orange (warning)
  ///   idle/offline   → gray  (neutral)
  Color _colorForStatus(String status) {
    switch (status.toLowerCase()) {
      case 'active':
      case 'driving':
        return AppColors.success;
      case 'stopped':
        return AppColors.warning;
      case 'idle':
      case 'offline':
        return AppColors.neutralText;
      default:
        return AppColors.info;
    }
  }
}

// ---------------------------------------------------------------------------
// Detail row — icon + label used in the bottom sheet
// ---------------------------------------------------------------------------

class _DetailRow extends StatelessWidget {
  final IconData icon;
  final String label;

  const _DetailRow({
    required this.icon,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: [
        Icon(
          icon,
          size: 18,
          color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Text(
            label,
            style: theme.textTheme.bodyMedium,
          ),
        ),
      ],
    );
  }
}
