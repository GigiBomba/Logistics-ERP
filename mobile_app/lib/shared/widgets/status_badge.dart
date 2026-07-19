import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';

/// A small chip that displays a transport status with the correct colors.
///
/// Provide a [statusKey] matching one of the defined statuses; the Romanian
/// label is used by default. Unknown keys fall back to a neutral style.
class StatusBadge extends StatelessWidget {
  const StatusBadge({
    super.key,
    required this.statusKey,
    this.label,
  });

  final String statusKey;
  final String? label;

  // ── Status definitions ────────────────────────

  static const Map<String, _StatusDef> _statusMap = {
    'delivered': _StatusDef('Livrat', AppColors.successText, AppColors.successSubtle),
    'planned': _StatusDef('Planificat', AppColors.accent, AppColors.accentSubtle),
    'in_progress': _StatusDef('În curs', AppColors.warningText, AppColors.warningSubtle),
    'in_transit': _StatusDef('În curs', AppColors.warningText, AppColors.warningSubtle),
    'cancelled': _StatusDef('Anulat', AppColors.neutralText, AppColors.neutralSubtle),
    'overdue': _StatusDef('Restant', AppColors.errorText, AppColors.errorSubtle),
    'maintenance': _StatusDef('Mentenanță', AppColors.infoText, AppColors.infoSubtle),
    'loading': _StatusDef('Se încarcă', AppColors.tertiary, AppColors.darkOverlay),
    'invoiced': _StatusDef('Facturat', AppColors.infoText, AppColors.infoSubtle),
    'paid': _StatusDef('Plătit', AppColors.successText, AppColors.successSubtle),
  };

  _StatusDef get _def => _statusMap[statusKey] ??
      _StatusDef(statusKey, AppColors.neutralText, AppColors.neutralSubtle);

  @override
  Widget build(BuildContext context) {
    final def = _def;
    final displayLabel = label ?? def.label;

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: def.bgColor,
        borderRadius: BorderRadius.circular(AppSpacing.xs),
      ),
      child: Text(
        displayLabel,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: def.textColor,
          height: 1.2,
        ),
      ),
    );
  }
}

class _StatusDef {
  const _StatusDef(this.label, this.textColor, this.bgColor);

  final String label;
  final Color textColor;
  final Color bgColor;
}
