import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_text_field.dart';

import 'expense_providers.dart';

/// Screen for creating a new driver expense.
///
/// Displays a form with expense type (segmented button), amount (with currency
/// prefix), date picker, and optional description. On submit, POSTs the data
/// to `/mobile/driver/expenses` and pops back on success.
class NewExpenseScreen extends ConsumerStatefulWidget {
  const NewExpenseScreen({super.key});

  @override
  ConsumerState<NewExpenseScreen> createState() => _NewExpenseScreenState();
}

class _NewExpenseScreenState extends ConsumerState<NewExpenseScreen> {
  final _formKey = GlobalKey<FormState>();
  final _amountController = TextEditingController();
  final _descriptionController = TextEditingController();

  /// Currently selected expense type.
  String _selectedType = 'fuel';

  /// Currently selected date (defaults to today).
  late DateTime _selectedDate;

  @override
  void initState() {
    super.initState();
    _selectedDate = DateTime.now();
  }

  @override
  void dispose() {
    _amountController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  // ── Expense type options ────────────────────────────────────────────────

  static const _expenseTypeOptions = [
    ('fuel', LucideIcons.fuel),
    ('tolls', LucideIcons.road),
    ('per_diem', LucideIcons.calendar),
    ('other', LucideIcons.receipt),
  ];

  // ── Date picker ─────────────────────────────────────────────────────────

  /// Opens a [DatePicker] and updates [_selectedDate] if the user picks a
  /// new date.
  Future<void> _pickDate(BuildContext context) async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: now.subtract(const Duration(days: 365)),
      lastDate: now,
      helpText: context.loc.expense_date,
    );
    if (picked != null && picked != _selectedDate) {
      setState(() => _selectedDate = picked);
    }
  }

  // ── Form submission ─────────────────────────────────────────────────────

  /// Validates the form and sends the expense data to the API.
  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    final loc = context.loc;
    final isSubmitting = ref.read(expenseSubmittingProvider);

    if (isSubmitting) return; // Prevent double tap

    ref.read(expenseSubmittingProvider.notifier).state = true;

    try {
      final client = ref.read(apiClientProvider);
      final amount = double.tryParse(_amountController.text) ?? 0.0;

      await client.post(
        '/mobile/driver/expenses',
        data: {
          'expense_type': _selectedType,
          'amount': amount,
          'currency': 'EUR',
          'date': DateFormat('yyyy-MM-dd').format(_selectedDate),
          'description': _descriptionController.text.trim(),
        },
      );

      if (!context.mounted) return;

      // Invalidate the expenses list so it re-fetches on return.
      ref.invalidate(expensesProvider);

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(loc.expense_submit),
          backgroundColor: AppColors.success,
        ),
      );
      Navigator.pop(context);
    } on DioException {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(loc.general_error),
          backgroundColor: AppColors.error,
        ),
      );
    } finally {
      if (mounted) {
        ref.read(expenseSubmittingProvider.notifier).state = false;
      }
    }
  }

  // ── Build ───────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final isSubmitting = ref.watch(expenseSubmittingProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.expense_new)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Expense type ──────────────────────────
              Text(
                loc.expense_type,
                style: theme.textTheme.labelLarge?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              SegmentedButton<String>(
                segments: _expenseTypeOptions.map((entry) {
                  final (value, icon) = entry;
                  return ButtonSegment<String>(
                    value: value,
                    label: Text(_typeLabel(loc, value)),
                    icon: Icon(icon, size: 18),
                  );
                }).toList(),
                selected: {_selectedType},
                onSelectionChanged: (selected) {
                  setState(() => _selectedType = selected.first);
                },
                showSelectedIcon: false,
              ),
              const SizedBox(height: AppSpacing.xl),

              // ── Amount ────────────────────────────────
              AppTextField(
                controller: _amountController,
                labelText: loc.expense_amount,
                keyboardType: TextInputType.numberWithOptions(decimal: true),
                textInputAction: TextInputAction.next,
                prefixIcon: const Text(
                  '€',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return '${loc.expense_amount} is required';
                  }
                  final amount = double.tryParse(value);
                  if (amount == null || amount <= 0) {
                    return '${loc.expense_amount} must be greater than 0';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppSpacing.lg),

              // ── Date ──────────────────────────────────
              Text(
                loc.expense_date,
                style: theme.textTheme.labelLarge?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              InkWell(
                onTap: () => _pickDate(context),
                borderRadius: AppRadius.lgAll,
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.md,
                  ),
                  decoration: BoxDecoration(
                    border: Border.all(
                      color: theme.colorScheme.outline,
                    ),
                    borderRadius: AppRadius.lgAll,
                  ),
                  child: Row(
                    children: [
                      Icon(
                        LucideIcons.calendar,
                        size: 20,
                        color: theme.colorScheme.primary,
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Text(
                        DateFormat.yMMMd().format(_selectedDate),
                        style: theme.textTheme.bodyLarge,
                      ),
                      const Spacer(),
                      Icon(
                        LucideIcons.chevronDown,
                        size: 20,
                        color: theme.colorScheme.onSurface
                            .withValues(alpha: 0.5),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.lg),

              // ── Description ───────────────────────────
              AppTextField(
                controller: _descriptionController,
                labelText: 'Description',
                hintText: 'Optional description',
                maxLines: 3,
                textInputAction: TextInputAction.newline,
              ),
              const SizedBox(height: AppSpacing.xxl),

              // ── Submit button ─────────────────────────
              AppButton.primary(
                label: loc.expense_submit,
                isLoading: isSubmitting,
                onPressed: _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Returns the localized label for the given expense [type].
  String _typeLabel(AppLocalizations loc, String type) {
    return switch (type) {
      'fuel' => loc.expense_fuel,
      'tolls' => loc.expense_tolls,
      'per_diem' => loc.expense_perDiem,
      _ => loc.expense_other,
    };
  }
}
