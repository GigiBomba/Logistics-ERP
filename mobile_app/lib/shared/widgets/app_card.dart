import 'package:flutter/material.dart';

import '../../core/theme/app_spacing.dart';

/// A consistent card widget that integrates with the Operion theme.
///
/// Provides a subtle border, rounded corners, and an optional tap ripple.
class AppCard extends StatelessWidget {
  const AppCard({
    super.key,
    required this.child,
    this.onTap,
    this.padding,
  });

  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry? padding;

  @override
  Widget build(BuildContext context) {
    final effectivePadding =
        padding ?? const EdgeInsets.all(AppSpacing.lg);

    final card = Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: effectivePadding,
        child: child,
      ),
    );

    if (onTap == null) return card;

    return InkWell(
      onTap: onTap,
      borderRadius: AppRadius.lgAll,
      child: card,
    );
  }
}
