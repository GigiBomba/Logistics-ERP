import 'package:flutter/material.dart';
import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../models/copilot_models.dart';

/// Bottom sheet for confirming Co-Pilot actions (§32.6).
///
/// Level 2+ requires an explicit tap, never voice-only confirmation.
/// Level 3 requires typing the confirmation phrase — biometrics are
/// additional, never a substitute.
class CopilotConfirmationSheet extends StatefulWidget {
  final CopilotExecutionPlan plan;
  final VoidCallback onConfirm;
  final VoidCallback onCancel;

  const CopilotConfirmationSheet({
    super.key,
    required this.plan,
    required this.onConfirm,
    required this.onCancel,
  });

  @override
  State<CopilotConfirmationSheet> createState() =>
      _CopilotConfirmationSheetState();
}

class _CopilotConfirmationSheetState
    extends State<CopilotConfirmationSheet> {
  final _phraseController = TextEditingController();
  bool _phraseMatch = false;

  @override
  void dispose() {
    _phraseController.dispose();
    super.dispose();
  }

  bool get _isDestructive =>
      widget.plan.steps.any((s) => s.confirmationLevel >= 3);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Handle
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.textTertiary,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // Title
          Text(
            context.loc.ai_confirmTitle,
            style: AppTypography.titleMedium,
          ),
          const SizedBox(height: AppSpacing.md),

          // Step summary
          ...widget.plan.steps.map((step) => _StepCard(step: step)),

          const SizedBox(height: AppSpacing.md),

          // Level 3: typed confirmation phrase
          if (_isDestructive) ...[
            Container(
              padding: const EdgeInsets.all(AppSpacing.sm),
              decoration: BoxDecoration(
                color: AppColors.error.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.error),
              ),
              child: Text(
                context.loc.copilot_level3_warning,
                style: AppTypography.bodySmall.copyWith(
                  color: AppColors.error,
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            TextField(
              controller: _phraseController,
              decoration: InputDecoration(
                hintText: context.loc.copilot_level3_hint,
                border: const OutlineInputBorder(),
              ),
              onChanged: (value) {
                setState(() {
                  _phraseMatch = value.trim() == widget.plan.confirmationPhrase;
                });
              },
            ),
            const SizedBox(height: AppSpacing.md),
          ],

          // Buttons
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: widget.onCancel,
                  child: Text(context.loc.general_cancel),
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: FilledButton(
                  onPressed: _isDestructive && !_phraseMatch
                      ? null
                      : widget.onConfirm,
                  child: Text(context.loc.general_confirm),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _StepCard extends StatelessWidget {
  final CopilotExecutionStep step;
  const _StepCard({required this.step});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          children: [
            Icon(
              step.confirmationLevel >= 3
                  ? Icons.warning_rounded
                  : Icons.info_outline,
              color: step.confirmationLevel >= 3
                  ? AppColors.error
                  : AppColors.warning,
              size: 20,
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(step.toolName,
                      style: AppTypography.bodyMedium),
                  if (step.parameters.isNotEmpty)
                    Text(
                      step.parameters.entries
                          .map((e) => '${e.key}=${e.value}')
                          .join(', '),
                      style: AppTypography.bodySmall.copyWith(
                        color: AppColors.textSecondary,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
