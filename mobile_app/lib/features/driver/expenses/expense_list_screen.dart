import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:intl/intl.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_state.dart';
import '../../../shared/widgets/shimmer_loader.dart';

import 'expense_providers.dart';
import 'new_expense_screen.dart';

/// Displays the current driver's list of expenses.
///
/// Fetches data from [expensesProvider] and renders each expense as an
/// [AppCard] with a color-coded icon, type label, amount, date, status chip,
/// and description. Supports pull-to-refresh and a FAB to create new expenses.
class ExpenseListScreen extends ConsumerWidget {
  const ExpenseListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final expensesAsync = ref.watch(expensesProvider);
    final loc = context.loc;

    final showFab = expensesAsync.maybeWhen(
      data: (expenses) => expenses.isNotEmpty,
      orElse: () => false,
    );

    return Scaffold(
      appBar: AppBar(title: Text(loc.driver_expenses)),
      body: expensesAsync.when(
        loading: () => const _LoadingState(),
        error: (error, stack) => _ErrorState(
          message: loc.general_error,
          onRetry: () => ref.invalidate(expensesProvider),
        ),
        data: (expenses) {
          if (expenses.isEmpty) {
            return _EmptyState(
              onNewExpense: () => _navigateToNewExpense(context),
            );
          }
          return _ExpenseList(
            expenses: expenses,
            onRefresh: () async {
              ref.invalidate(expensesProvider);
              await ref.read(expensesProvider.future);
            },
            onNewExpense: () => _navigateToNewExpense(context),
          );
        },
      ),
      floatingActionButton: showFab
          ? FloatingActionButton(
              onPressed: () => _navigateToNewExpense(context),
              child: const Icon(LucideIcons.plus),
            )
          : null,
    );
  }

  /// Navigates to [NewExpenseScreen].
  void _navigateToNewExpense(BuildContext context) {
    Navigator.push(
      context,
      MaterialPageRoute<void>(
        builder: (_) => const NewExpenseScreen(),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

/// Shows a list of [ShimmerCard] placeholders while expenses are loading.
class _LoadingState extends StatelessWidget {
  const _LoadingState();

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      padding: const EdgeInsets.all(AppSpacing.lg),
      itemCount: 5,
      itemBuilder: (_, __) => const Padding(
        padding: EdgeInsets.only(bottom: AppSpacing.sm),
        child: ShimmerCard(),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

/// Displays an error message with a retry button.
class _ErrorState extends StatelessWidget {
  const _ErrorState({
    required this.message,
    required this.onRetry,
  });

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              LucideIcons.alertCircle,
              size: 48,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: AppSpacing.lg),
            Text(
              message,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            const SizedBox(height: AppSpacing.lg),
            FilledButton.tonalIcon(
              onPressed: onRetry,
              icon: const Icon(LucideIcons.refreshCw),
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

/// Shows an [EmptyState] with a FAB-style button to create the first expense.
class _EmptyState extends StatelessWidget {
  const _EmptyState({
    required this.onNewExpense,
  });

  final VoidCallback onNewExpense;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          EmptyState(
            icon: const Icon(LucideIcons.receipt),
            title: loc.driver_expenses,
            subtitle: 'No expenses yet',
          ),
          const SizedBox(height: AppSpacing.lg),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xxl),
            child: FilledButton.tonalIcon(
              onPressed: onNewExpense,
              icon: const Icon(LucideIcons.plus),
              label: Text(loc.expense_new),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Expense list
// ---------------------------------------------------------------------------

/// The main expense list with pull-to-refresh and a FAB.
class _ExpenseList extends StatelessWidget {
  const _ExpenseList({
    required this.expenses,
    required this.onRefresh,
    required this.onNewExpense,
  });

  final List<Map<String, dynamic>> expenses;
  final Future<void> Function() onRefresh;
  final VoidCallback onNewExpense;

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: onRefresh,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.lg,
          AppSpacing.lg,
          AppSpacing.lg,
          AppSpacing.giant, // Extra bottom padding for FAB
        ),
        itemCount: expenses.length,
        separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
        itemBuilder: (context, index) {
          final expense = expenses[index];
          return _ExpenseCard(expense: expense);
        },
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Expense card
// ---------------------------------------------------------------------------

/// A single expense item rendered as an [AppCard].
class _ExpenseCard extends StatelessWidget {
  const _ExpenseCard({required this.expense});

  final Map<String, dynamic> expense;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final theme = Theme.of(context);

    final type = expense['expense_type'] as String? ?? 'other';
    final amount = (expense['amount'] as num?)?.toDouble() ?? 0.0;
    final currency = expense['currency'] as String? ?? 'EUR';
    final dateStr = expense['date'] as String? ?? '';
    final description = expense['description'] as String?;
    final status = expense['status'] as String? ?? 'pending';

    // Parse date for display
    final DateTime? date = dateStr.isNotEmpty ? DateTime.tryParse(dateStr) : null;
    final formattedDate = date != null
        ? DateFormat.yMMMd().format(date)
        : '';

    // Color-coded icon by expense type
    final (IconData icon, Color iconColor, Color iconBg) = switch (type) {
      'fuel' => (
        LucideIcons.fuel,
        AppColors.warning,
        AppColors.warningSubtle,
      ),
      'tolls' => (
        LucideIcons.road,
        AppColors.info,
        AppColors.infoSubtle,
      ),
      'per_diem' => (
        LucideIcons.calendar,
        AppColors.success,
        AppColors.successSubtle,
      ),
      _ => (
        LucideIcons.receipt,
        AppColors.neutralText,
        AppColors.neutralSubtle,
      ),
    };

    // Status chip styling
    final (Color statusColor, String statusLabel) = switch (status) {
      'approved' => (AppColors.success, 'Approved'),
      'rejected' => (AppColors.error, 'Rejected'),
      _ => (AppColors.warning, 'Pending'),
    };

    // Localized type label
    final typeLabel = switch (type) {
      'fuel' => loc.expense_fuel,
      'tolls' => loc.expense_tolls,
      'per_diem' => loc.expense_perDiem,
      _ => loc.expense_other,
    };

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Top row: icon, type, amount ──────────────
          Row(
            children: [
              // Color-coded icon container
              Container(
                height: 44,
                width: 44,
                decoration: BoxDecoration(
                  color: iconBg,
                  borderRadius: AppRadius.lgAll,
                ),
                child: Icon(icon, color: iconColor, size: 22),
              ),
              const SizedBox(width: AppSpacing.md),
              // Type label
              Expanded(
                child: Text(
                  typeLabel,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              // Amount (bold, right-aligned)
              Text(
                '${NumberFormat.currency(symbol: currency).format(amount)}',
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),

          // ── Date ─────────────────────────────────────
          Text(
            formattedDate,
            style: theme.textTheme.bodySmall?.copyWith(
              color: AppColors.textSecondaryLight,
            ),
          ),
          const SizedBox(height: AppSpacing.sm),

          // ── Bottom row: description + status chip ────
          Row(
            children: [
              // Description (1 line, gray)
              Expanded(
                child: Text(
                  description ?? '',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AppColors.neutralText,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              // Status chip
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.sm,
                  vertical: AppSpacing.xs,
                ),
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.12),
                  borderRadius: AppRadius.pillAll,
                ),
                child: Text(
                  statusLabel,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: statusColor,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
