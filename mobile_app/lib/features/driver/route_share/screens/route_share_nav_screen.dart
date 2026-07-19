import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/auth/auth_providers.dart';
import '../../../../core/i18n/app_localizations.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../shared/widgets/empty_state.dart';
import '../../../../shared/widgets/shimmer_loader.dart';
import '../../../../shared/widgets/turn_instruction_banner.dart';
import '../../models/route_share_geometry.dart';
import '../providers/route_share_providers.dart';

/// Full-screen turn-by-turn navigation using phone GPS.
///
/// Renders a flutter_map with the route polyline, current position marker,
/// instruction banner, and bottom sheet with remaining distance/time.
/// Handles loading, error, empty (no route data), and offline states.
class RouteShareNavScreen extends ConsumerWidget {
  const RouteShareNavScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOffline = ref.watch(isOfflineProvider);
    final geometryAsync = ref.watch(routeShareGeometryProvider);

    return Scaffold(
      body: Column(
        children: [
          Expanded(
            child: RefreshIndicator(
              onRefresh: () async {
                ref.invalidate(routeShareGeometryProvider);
                await ref.read(routeShareGeometryProvider.future);
              },
              child: geometryAsync.when(
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (error, _) => _ErrorView(
                  message: error.toString(),
                  onRetry: () => ref.invalidate(routeShareGeometryProvider),
                ),
                data: (geometry) => geometry.points.isEmpty
                    ? const _EmptyRouteView()
                    : _RouteMapView(geometry: geometry, isOffline: isOffline),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(LucideIcons.alertCircle, size: 48, color: AppColors.error),
            const SizedBox(height: AppSpacing.lg),
            Text(loc.general_error),
            const SizedBox(height: AppSpacing.sm),
            Text(message, textAlign: TextAlign.center, maxLines: 3),
            const SizedBox(height: AppSpacing.lg),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh, size: 18),
              label: Text(loc.general_retry),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

class _EmptyRouteView extends StatelessWidget {
  const _EmptyRouteView();

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    return Center(
      child: EmptyState(
        icon: const Icon(Icons.map, size: 56),
        title: loc.routeShare_noData,
        subtitle: loc.routeShare_noDataSubtitle,
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Route map view
// ---------------------------------------------------------------------------

class _RouteMapView extends ConsumerStatefulWidget {
  final RouteShareGeometry geometry;
  final bool isOffline;
  const _RouteMapView({required this.geometry, required this.isOffline});

  @override
  ConsumerState<_RouteMapView> createState() => _RouteMapViewState();
}

class _RouteMapViewState extends ConsumerState<_RouteMapView> {
  final MapController _mapController = MapController();

  List<LatLng> get _routePoints =>
      widget.geometry.points.map((p) => LatLng(p.lat, p.lng)).toList();

  @override
  void initState() {
    super.initState();
    // Fit map to route bounds after first frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_routePoints.isNotEmpty) {
        _mapController.fitCamera(
          CameraFit.bounds(
            bounds: LatLngBounds.fromPoints(_routePoints),
            padding: const EdgeInsets.all(50),
          ),
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final points = _routePoints;

    return Stack(
      children: [
        // ── Full-screen map ──
        FlutterMap(
          mapController: _mapController,
          options: MapOptions(
            initialCenter: points.isNotEmpty
                ? points.first
                : const LatLng(46.0, 25.0),
            initialZoom: 12.0,
          ),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              userAgentPackageName: 'com.operion.mobile',
            ),
            if (points.isNotEmpty)
              PolylineLayer(
                polylines: [
                  Polyline(
                    points: points,
                    color: AppColors.accent,
                    strokeWidth: 4.0,
                  ),
                ],
              ),
            if (points.isNotEmpty)
              MarkerLayer(
                markers: [
                  // Start marker
                  Marker(
                    point: points.first,
                    width: 30,
                    height: 30,
                    child: const Icon(Icons.trip_origin,
                        color: AppColors.success, size: 30),
                  ),
                  // End marker
                  Marker(
                    point: points.last,
                    width: 30,
                    height: 30,
                    child: const Icon(Icons.location_on,
                        color: AppColors.error, size: 30),
                  ),
                ],
              ),
          ],
        ),

        // ── Instruction banner at top ──
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: TurnInstructionBanner(
              instructionText: widget.geometry.instructions.isNotEmpty
                  ? widget.geometry.instructions.first.textKey
                  : null,
              distanceMeters: widget.geometry.totalDistanceMeters,
              etaText: _formatDuration(widget.geometry.totalDurationSeconds),
            ),
          ),
        ),

        // ── Bottom sheet: remaining distance/time ──
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          child: _BottomInfoBar(
            distanceMeters: widget.geometry.totalDistanceMeters,
            durationSeconds: widget.geometry.totalDurationSeconds,
          ),
        ),
      ],
    );
  }

  String _formatDuration(int totalSeconds) {
    final hours = totalSeconds ~/ 3600;
    final minutes = (totalSeconds % 3600) ~/ 60;
    if (hours > 0) return '${hours}h ${minutes}m';
    return '${minutes}m';
  }

  @override
  void dispose() {
    _mapController.dispose();
    super.dispose();
  }
}

// ---------------------------------------------------------------------------
// Bottom info bar
// ---------------------------------------------------------------------------

class _BottomInfoBar extends StatelessWidget {
  final double distanceMeters;
  final int durationSeconds;
  const _BottomInfoBar(
      {required this.distanceMeters, required this.durationSeconds});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final loc = context.loc;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.md,
      ),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(AppRadius.xl)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 8,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _InfoItem(
              icon: LucideIcons.map,
              label: loc.routeShare_distance,
              value: _formatDistance(distanceMeters),
            ),
            _InfoItem(
              icon: LucideIcons.clock,
              label: loc.routeShare_estimatedTime,
              value: _formatDuration(durationSeconds),
            ),
          ],
        ),
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

class _InfoItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  const _InfoItem(
      {required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 20, color: AppColors.accent),
        const SizedBox(height: AppSpacing.xs),
        Text(
          label,
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
          ),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: theme.textTheme.titleMedium
              ?.copyWith(fontWeight: FontWeight.bold),
        ),
      ],
    );
  }
}
