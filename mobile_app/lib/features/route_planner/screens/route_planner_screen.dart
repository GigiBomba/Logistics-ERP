import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_text_field.dart';
import '../../../shared/widgets/empty_state.dart';

/// Route Planner screen — multi-stop trip planning with drag-to-reorder.
///
/// Users add/remove/reorder waypoints, then submit for optimized route.
/// The optimized route renders on a flutter_map view.
class RoutePlannerScreen extends ConsumerStatefulWidget {
  const RoutePlannerScreen({super.key});

  @override
  ConsumerState<RoutePlannerScreen> createState() => _RoutePlannerScreenState();
}

class _RoutePlannerScreenState extends ConsumerState<RoutePlannerScreen> {
  final List<String> _waypoints = [];
  final _originController = TextEditingController();
  final _destinationController = TextEditingController();

  @override
  void dispose() {
    _originController.dispose();
    _destinationController.dispose();
    super.dispose();
  }

  void _addWaypoint() {
    setState(() => _waypoints.add(''));
  }

  void _removeWaypoint(int index) {
    setState(() => _waypoints.removeAt(index));
  }

  void _showRouteResult(BuildContext context, ThemeData theme) {
    final loc = context.loc;
    // Mock route data — will be replaced with backend response
    final mockPoints = [
      const LatLng(44.4268, 26.1025), // Bucharest center
      const LatLng(44.4368, 26.1125),
      const LatLng(44.4468, 26.1225),
      const LatLng(44.4568, 26.1325),
    ];
    const mockDistance = 12450.0; // meters
    const mockDuration = 840; // seconds

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.xl)),
      ),
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.85,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        expand: false,
        builder: (_, scrollController) => _RouteOptimizationResult(
          waypoints: mockPoints,
          distanceMeters: mockDistance,
          durationSeconds: mockDuration,
          originLabel: _originController.text,
          destinationLabel: _destinationController.text,
          scrollController: scrollController,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.nav_routePlanner)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Origin
            Text(loc.routePlanner_origin, style: theme.textTheme.titleSmall),
            const SizedBox(height: AppSpacing.sm),
            AppTextField(
              controller: _originController,
              hintText: loc.routePlanner_originHint,
              prefixIcon: const Icon(Icons.trip_origin, size: 20),
            ),
            const SizedBox(height: AppSpacing.lg),

            // Destination
            Text(loc.routePlanner_destination, style: theme.textTheme.titleSmall),
            const SizedBox(height: AppSpacing.sm),
            AppTextField(
              controller: _destinationController,
              hintText: loc.routePlanner_destinationHint,
              prefixIcon: const Icon(Icons.location_on, size: 20),
            ),
            const SizedBox(height: AppSpacing.lg),

            // Waypoints
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('${loc.routePlanner_stops} (${_waypoints.length})', style: theme.textTheme.titleSmall),
                TextButton.icon(
                  onPressed: _addWaypoint,
                  icon: const Icon(LucideIcons.plus, size: 18),
                  label: Text(loc.routePlanner_addStop),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),

            if (_waypoints.isEmpty)
              EmptyState(
                icon: const Icon(LucideIcons.mapPin, size: 48),
                title: loc.routePlanner_noStops,
                subtitle: loc.routePlanner_noStopsHint,
              )
            else
              ReorderableListView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: _waypoints.length,
                onReorder: (oldIndex, newIndex) {
                  setState(() {
                    if (newIndex > oldIndex) newIndex--;
                    final item = _waypoints.removeAt(oldIndex);
                    _waypoints.insert(newIndex, item);
                  });
                },
                itemBuilder: (context, index) {
                  return Card(
                    key: ValueKey('waypoint_$index'),
                    margin: const EdgeInsets.only(bottom: AppSpacing.sm),
                    child: ListTile(
                      leading: Icon(LucideIcons.gripVertical, size: 20),
                      title: Text('${loc.routePlanner_stopNumber} ${index + 1}'),
                      trailing: IconButton(
                        icon: const Icon(LucideIcons.trash2, size: 18),
                        onPressed: () => _removeWaypoint(index),
                      ),
                    ),
                  );
                },
              ),

            const SizedBox(height: AppSpacing.xxl),

            // Submit button
            AppButton.primary(
              label: loc.routePlanner_optimize,
              onPressed: _originController.text.isNotEmpty && _destinationController.text.isNotEmpty
                  ? () => _showRouteResult(context, theme)
                  : null,
            ),

            const SizedBox(height: AppSpacing.xhuge),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Route optimization result — full-screen bottom sheet content
// ---------------------------------------------------------------------------

class _RouteOptimizationResult extends StatelessWidget {
  final List<LatLng> waypoints;
  final double distanceMeters;
  final int durationSeconds;
  final String originLabel;
  final String destinationLabel;
  final ScrollController scrollController;

  const _RouteOptimizationResult({
    required this.waypoints,
    required this.distanceMeters,
    required this.durationSeconds,
    required this.originLabel,
    required this.destinationLabel,
    required this.scrollController,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final loc = context.loc;

    return SingleChildScrollView(
      controller: scrollController,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Handle ──
          Center(
            child: Container(
              margin: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.textTertiary,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),

          // ── Title ──
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
            child: Text(
              loc.routePlanner_optimize,
              style: theme.textTheme.titleLarge,
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // ── Map ──
          SizedBox(
            height: 240,
            child: FlutterMap(
              options: MapOptions(
                initialCenter: waypoints.isNotEmpty
                    ? waypoints.first
                    : const LatLng(44.4268, 26.1025),
                initialZoom: 13.0,
              ),
              children: [
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'com.operion.mobile',
                ),
                if (waypoints.length >= 2)
                  PolylineLayer(
                    polylines: [
                      Polyline(
                        points: waypoints,
                        color: AppColors.accent,
                        strokeWidth: 4.0,
                      ),
                    ],
                  ),
                if (waypoints.isNotEmpty)
                  MarkerLayer(
                    markers: [
                      Marker(
                        point: waypoints.first,
                        width: 30,
                        height: 30,
                        child: const Icon(Icons.trip_origin,
                            color: AppColors.success, size: 30),
                      ),
                      Marker(
                        point: waypoints.last,
                        width: 30,
                        height: 30,
                        child: const Icon(Icons.location_on,
                            color: AppColors.error, size: 30),
                      ),
                    ],
                  ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // ── Distance / Time summary ──
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
            child: Row(
              children: [
                Expanded(
                  child: _SummaryTile(
                    icon: LucideIcons.map,
                    label: loc.routeShare_distance,
                    value: _formatDistance(distanceMeters),
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: _SummaryTile(
                    icon: LucideIcons.clock,
                    label: loc.routeShare_estimatedTime,
                    value: _formatDuration(durationSeconds),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // ── Waypoint list ──
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
            child: Text(
              loc.routePlanner_stops,
              style: theme.textTheme.titleSmall,
            ),
          ),
          const SizedBox(height: AppSpacing.sm),

          // Origin
          _WaypointTile(
            index: 0,
            label: originLabel,
            icon: Icons.trip_origin,
            iconColor: AppColors.success,
          ),

          // Intermediate waypoints (mock for now)
          ...waypoints.asMap().entries.map((entry) {
            if (entry.key == 0 || entry.key == waypoints.length - 1) {
              return const SizedBox.shrink();
            }
            return _WaypointTile(
              index: entry.key,
              label: '${loc.routePlanner_stopNumber} ${entry.key + 1}',
              icon: LucideIcons.mapPin,
              iconColor: AppColors.accent,
            );
          }),

          // Destination
          _WaypointTile(
            index: waypoints.length - 1,
            label: destinationLabel,
            icon: Icons.location_on,
            iconColor: AppColors.error,
          ),

          const SizedBox(height: AppSpacing.lg),

          // ── Backend notice ──
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
            child: Container(
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: AppColors.info.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(AppRadius.lg),
                border: Border.all(color: AppColors.info.withValues(alpha: 0.3)),
              ),
              child: Row(
                children: [
                  Icon(LucideIcons.info, size: 18, color: AppColors.info),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      'Route optimization will connect to the backend',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: AppColors.info,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: AppSpacing.xxl),
        ],
      ),
    );
  }

  String _formatDistance(double meters) {
    if (meters >= 1000) return '${(meters / 1000).toStringAsFixed(1)} km';
    return '${meters.toInt()} m';
  }

  String _formatDuration(int totalSeconds) {
    final hours = totalSeconds ~/ 3600;
    final minutes = (totalSeconds % 3600) ~/ 60;
    if (hours > 0) return '${hours}h ${minutes}m';
    return '${minutes}m';
  }
}

class _SummaryTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _SummaryTile({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        border: Border.all(color: AppColors.divider),
      ),
      child: Column(
        children: [
          Icon(icon, size: 22, color: AppColors.accent),
          const SizedBox(height: AppSpacing.xs),
          Text(
            label,
            style: theme.textTheme.bodySmall?.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}

class _WaypointTile extends StatelessWidget {
  final int index;
  final String label;
  final IconData icon;
  final Color iconColor;

  const _WaypointTile({
    required this.index,
    required this.label,
    required this.icon,
    required this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.xs,
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 14,
            backgroundColor: iconColor.withValues(alpha: 0.15),
            child: Icon(icon, size: 16, color: iconColor),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Text(
              label,
              style: theme.textTheme.bodyMedium,
            ),
          ),
          Text(
            '#${index + 1}',
            style: theme.textTheme.bodySmall?.copyWith(
              color: AppColors.textTertiary,
            ),
          ),
        ],
      ),
    );
  }
}
