import 'package:flutter/material.dart';
import 'package:shimmer/shimmer.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';

/// A generic shimmer / skeleton loading wrapper.
///
/// Wraps [child] in a shimmer effect. Use [ShimmerCard] for a ready-made
/// card-shaped placeholder for list items.
class ShimmerLoader extends StatelessWidget {
  const ShimmerLoader({
    super.key,
    required this.child,
  });

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Shimmer.fromColors(
      baseColor: isDark ? AppColors.darkOverlay : const Color(0xFFE0E0E0),
      highlightColor:
          isDark ? AppColors.darkSurface : const Color(0xFFF5F5F5),
      child: child,
    );
  }
}

/// A pre-built card-shaped shimmer placeholder suitable for list items.
class ShimmerCard extends StatelessWidget {
  const ShimmerCard({super.key});

  @override
  Widget build(BuildContext context) {
    return const ShimmerLoader(
      child: Card(
        margin: EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.xs,
        ),
        child: Padding(
          padding: EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _ShimmerLine(width: 0.6),
              SizedBox(height: AppSpacing.sm),
              _ShimmerLine(width: 0.9),
              SizedBox(height: AppSpacing.xs),
              _ShimmerLine(width: 0.4),
            ],
          ),
        ),
      ),
    );
  }
}

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
