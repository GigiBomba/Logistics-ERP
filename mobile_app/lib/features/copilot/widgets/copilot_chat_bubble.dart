import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';

/// A single chat bubble in the Co-Pilot conversation.
/// Renders user messages (right-aligned) and AI responses (left-aligned).
class CopilotChatBubble extends StatelessWidget {
  final String text;
  final bool isUser;
  final String? statusLabel;

  const CopilotChatBubble({
    super.key,
    required this.text,
    this.isUser = false,
    this.statusLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.xs,
      ),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) const _AiAvatar(),
          const SizedBox(width: AppSpacing.sm),
          Flexible(
            child: Container(
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: isUser
                    ? AppColors.primary
                    : AppColors.surfaceVariant,
                borderRadius: BorderRadius.circular(16).copyWith(
                  bottomLeft: isUser ? const Radius.circular(16) : Radius.zero,
                  bottomRight:
                      isUser ? Radius.zero : const Radius.circular(16),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    text,
                    style: AppTypography.bodyMedium.copyWith(
                      color: isUser ? AppColors.onPrimary : AppColors.textPrimary,
                    ),
                  ),
                  if (statusLabel != null) ...[
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      statusLabel!,
                      style: AppTypography.labelSmall.copyWith(
                        color: isUser
                            ? AppColors.onPrimary.withValues(alpha: 0.7)
                            : AppColors.textSecondary,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          if (isUser) const SizedBox(width: AppSpacing.sm),
        ],
      ),
    );
  }
}

class _AiAvatar extends StatelessWidget {
  const _AiAvatar();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 32,
      height: 32,
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Icon(
        Icons.auto_awesome,
        size: 18,
        color: AppColors.primary,
      ),
    );
  }
}
