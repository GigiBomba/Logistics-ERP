import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';

/// Three button variants following Operion's design system.
///
/// - [AppButton.primary]: filled indigo button
/// - [AppButton.secondary]: outlined button
/// - [AppButton.danger]: red outlined button
class AppButton extends StatelessWidget {
  const AppButton._({
    super.key,
    required this.label,
    required this.onPressed,
    required this.isLoading,
    required this.style,
    this.icon,
  });

  // ── Primary ──────────────────────────────────

  factory AppButton.primary({
    Key? key,
    required String label,
    required VoidCallback? onPressed,
    Widget? icon,
    bool isLoading = false,
  }) {
    return AppButton._(
      key: key,
      label: label,
      onPressed: onPressed,
      icon: icon,
      isLoading: isLoading,
      style: _ButtonStyle.primary,
    );
  }

  // ── Secondary ────────────────────────────────

  factory AppButton.secondary({
    Key? key,
    required String label,
    required VoidCallback? onPressed,
    Widget? icon,
    bool isLoading = false,
  }) {
    return AppButton._(
      key: key,
      label: label,
      onPressed: onPressed,
      icon: icon,
      isLoading: isLoading,
      style: _ButtonStyle.secondary,
    );
  }

  // ── Danger ───────────────────────────────────

  factory AppButton.danger({
    Key? key,
    required String label,
    required VoidCallback? onPressed,
    Widget? icon,
    bool isLoading = false,
  }) {
    return AppButton._(
      key: key,
      label: label,
      onPressed: onPressed,
      icon: icon,
      isLoading: isLoading,
      style: _ButtonStyle.danger,
    );
  }

  // ── Fields ───────────────────────────────────

  final String label;
  final VoidCallback? onPressed;
  final Widget? icon;
  final bool isLoading;
  final _ButtonStyle style;

  // ── Build ────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final child = isLoading
        ? const SizedBox(
            height: 20,
            width: 20,
            child: CircularProgressIndicator(strokeWidth: 2),
          )
        : Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[icon!, const SizedBox(width: AppSpacing.sm)],
              Text(label),
            ],
          );

    return SizedBox(
      width: double.infinity,
      height: 48,
      child: switch (style) {
        _ButtonStyle.primary => ElevatedButton(
            onPressed: isLoading ? null : onPressed,
            child: child,
          ),
        _ButtonStyle.secondary => OutlinedButton(
            onPressed: isLoading ? null : onPressed,
            child: child,
          ),
        _ButtonStyle.danger => OutlinedButton(
            onPressed: isLoading ? null : onPressed,
            style: OutlinedButton.styleFrom(
              foregroundColor: AppColors.error,
              side: const BorderSide(color: AppColors.error),
            ),
            child: child,
          ),
      },
    );
  }
}

enum _ButtonStyle { primary, secondary, danger }
