import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';

/// A banner showing the next turn instruction and distance.
///
/// Positioned at the top of the route-share navigation screen.
/// Shows the instruction text (resolved from i18n key) and the distance
/// to the next maneuver point.
class TurnInstructionBanner extends StatelessWidget {
  final String? instructionText;
  final double? distanceMeters;
  final String? etaText;

  const TurnInstructionBanner({
    super.key,
    this.instructionText,
    this.distanceMeters,
    this.etaText,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.md,
      ),
      decoration: BoxDecoration(
        color: AppColors.accent,
        borderRadius: AppRadius.xlAll,
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                if (instructionText != null)
                  Text(
                    instructionText!,
                    style: theme.textTheme.titleMedium?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                if (distanceMeters != null) ...[
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    _formatDistance(distanceMeters!),
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: Colors.white.withValues(alpha: 0.8),
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (etaText != null)
            Text(
              etaText!,
              style: theme.textTheme.titleLarge?.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
        ],
      ),
    );
  }

  String _formatDistance(double meters) {
    if (meters >= 1000) {
      return '${(meters / 1000).toStringAsFixed(1)} km';
    }
    return '${meters.toInt()} m';
  }
}
