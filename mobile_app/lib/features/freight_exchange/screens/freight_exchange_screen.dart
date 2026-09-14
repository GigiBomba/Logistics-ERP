import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/app_text_field.dart';
import '../../../shared/widgets/empty_state.dart';
import '../models/freight_load.dart';
import '../providers/freight_exchange_providers.dart';

/// Freight Exchange screen — browse and accept external loads.
///
/// Consumes the provider-agnostic backend endpoint.
class FreightExchangeScreen extends ConsumerStatefulWidget {
  const FreightExchangeScreen({super.key});

  @override
  ConsumerState<FreightExchangeScreen> createState() =>
      _FreightExchangeScreenState();
}

class _FreightExchangeScreenState extends ConsumerState<FreightExchangeScreen> {
  final _originController = TextEditingController();
  final _destinationController = TextEditingController();
  final _dateController = TextEditingController();
  final _cargoTypeController = TextEditingController();

  @override
  void dispose() {
    _originController.dispose();
    _destinationController.dispose();
    _dateController.dispose();
    _cargoTypeController.dispose();
    super.dispose();
  }

  Future<void> _applyFilters() async {
    FocusScope.of(context).unfocus();
    await ref.read(freightExchangeStateProvider.notifier).loadLoads(
          origin: _originController.text.trim(),
          destination: _destinationController.text.trim(),
          date: _dateController.text.trim(),
          cargoType: _cargoTypeController.text.trim(),
        );
  }

  void _showDetailSheet(FreightLoad load) {
    final loc = context.loc;
    final messenger = ScaffoldMessenger.of(context);
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.lg)),
      ),
      builder: (context) => _LoadDetailSheet(
        load: load,
        onImport: () async {
          Navigator.of(context).pop();
          await ref
              .read(freightExchangeStateProvider.notifier)
              .importLoad(load);
          if (mounted) {
            messenger.showSnackBar(
              SnackBar(content: Text(loc.freightExchange_import)),
            );
          }
        },
        onEvaluate: () async {
          Navigator.of(context).pop();
          final result = await ref
              .read(freightExchangeStateProvider.notifier)
              .evaluateLoad(load);
          if (mounted) {
            final message = result != null
                ? loc.freightExchange_evaluationComplete
                : loc.freightExchange_error;
            messenger.showSnackBar(
              SnackBar(content: Text(message)),
            );
          }
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final state = ref.watch(freightExchangeStateProvider);

    ref.listen<FreightExchangeState>(freightExchangeStateProvider, (_, next) {
      if (next is FreightExchangeError) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(loc.freightExchange_error)),
        );
      }
    });

    return Scaffold(
      appBar: AppBar(title: Text(loc.nav_freightExchange)),
      body: Column(
        children: [
          // Filter bar
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: AppTextField(
                        controller: _originController,
                        hintText: loc.freightExchange_filterOrigin,
                        prefixIcon: const Icon(LucideIcons.mapPin, size: 18),
                        textInputAction: TextInputAction.next,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: AppTextField(
                        controller: _destinationController,
                        hintText: loc.freightExchange_filterDestination,
                        prefixIcon: const Icon(LucideIcons.mapPin, size: 18),
                        textInputAction: TextInputAction.next,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.sm),
                Row(
                  children: [
                    Expanded(
                      child: AppTextField(
                        controller: _dateController,
                        hintText: loc.freightExchange_filterDate,
                        prefixIcon: const Icon(LucideIcons.calendar, size: 18),
                        keyboardType: TextInputType.datetime,
                        textInputAction: TextInputAction.next,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: AppTextField(
                        controller: _cargoTypeController,
                        hintText: loc.freightExchange_filterCargoType,
                        prefixIcon:
                            const Icon(LucideIcons.package, size: 18),
                        textInputAction: TextInputAction.search,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.sm),
                SizedBox(
                  width: double.infinity,
                  height: 44,
                  child: ElevatedButton.icon(
                    onPressed: _applyFilters,
                    icon: const Icon(LucideIcons.search, size: 18),
                    label: Text(loc.freightExchange_searchHint),
                  ),
                ),
              ],
            ),
          ),
          // Results
          Expanded(
            child: _Body(
              state: state,
              onRefresh: () async {
                final current = ref.read(freightExchangeStateProvider);
                if (current is FreightExchangeData) {
                  await ref
                      .read(freightExchangeStateProvider.notifier)
                      .refresh(
                        origin: current.origin,
                        destination: current.destination,
                        date: current.date,
                        cargoType: current.cargoType,
                      );
                } else {
                  await _applyFilters();
                }
              },
              onTapLoad: _showDetailSheet,
            ),
          ),
        ],
      ),
    );
  }
}

class _Body extends StatelessWidget {
  final FreightExchangeState state;
  final Future<void> Function() onRefresh;
  final ValueChanged<FreightLoad> onTapLoad;

  const _Body({
    required this.state,
    required this.onRefresh,
    required this.onTapLoad,
  });

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;

    return switch (state) {
      FreightExchangeInitial() => EmptyState(
          icon: const Icon(LucideIcons.search, size: 56),
          title: loc.freightExchange_empty,
          subtitle: loc.freightExchange_emptyHint,
        ),
      FreightExchangeLoading() =>
        const Center(child: CircularProgressIndicator()),
      FreightExchangeError(messageKey: final messageKey) => EmptyState(
          icon: const Icon(LucideIcons.alertCircle, size: 56),
          title: messageKey.isNotEmpty
              ? loc.lookup(messageKey)
              : loc.freightExchange_error,
          subtitle: loc.freightExchange_emptyHint,
        ),
      FreightExchangeData(loads: final loads) => loads.isEmpty
          ? EmptyState(
              icon: const Icon(LucideIcons.search, size: 56),
              title: loc.freightExchange_noLoadsFound,
              subtitle: loc.freightExchange_emptyHint,
            )
          : RefreshIndicator(
              onRefresh: onRefresh,
              child: ListView.builder(
                padding:
                    const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                itemCount: loads.length,
                itemBuilder: (context, index) {
                  final load = loads[index];
                  return Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.md),
                    child: AppCard(
                      onTap: () => onTapLoad(load),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  load.origin,
                                  style: AppTypography.bodyMedium.copyWith(
                                    fontWeight: FontWeight.w600,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              const Padding(
                                padding: EdgeInsets.symmetric(
                                    horizontal: AppSpacing.sm),
                                child: Icon(
                                  Icons.arrow_forward,
                                  size: 16,
                                  color: AppColors.textSecondary,
                                ),
                              ),
                              Expanded(
                                child: Text(
                                  load.destination,
                                  style: AppTypography.bodyMedium.copyWith(
                                    fontWeight: FontWeight.w600,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  textAlign: TextAlign.end,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: AppSpacing.sm),
                          Wrap(
                            spacing: AppSpacing.md,
                            runSpacing: AppSpacing.sm,
                            children: [
                              if (load.price != null)
                                _InfoChip(
                                  icon: LucideIcons.euro,
                                  label:
                                      '${load.price!.toStringAsFixed(2)} ${load.currency ?? ''}',
                                ),
                              if (load.pickupDate != null)
                                _InfoChip(
                                  icon: LucideIcons.calendar,
                                  label: DateFormat.yMd()
                                      .format(load.pickupDate!),
                                ),
                              if (load.weightKg != null)
                                _InfoChip(
                                  icon: LucideIcons.scale,
                                  label:
                                      '${load.weightKg!.toStringAsFixed(0)} kg',
                                ),
                              if (load.distanceKm != null)
                                _InfoChip(
                                  icon: LucideIcons.route,
                                  label: '${load.distanceKm} km',
                                ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
    };
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;

  const _InfoChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: AppColors.textSecondary),
        const SizedBox(width: AppSpacing.xs),
        Text(
          label,
          style: AppTypography.bodySmall
              .copyWith(color: AppColors.textSecondary),
        ),
      ],
    );
  }
}

class _LoadDetailSheet extends StatelessWidget {
  final FreightLoad load;
  final VoidCallback onImport;
  final VoidCallback onEvaluate;

  const _LoadDetailSheet({
    required this.load,
    required this.onImport,
    required this.onEvaluate,
  });

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;

    return Padding(
      padding: EdgeInsets.only(
        left: AppSpacing.lg,
        right: AppSpacing.lg,
        top: AppSpacing.lg,
        bottom: AppSpacing.lg + MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
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
          Text(
            loc.freightExchange_detailTitle,
            style: AppTypography.titleMedium,
          ),
          const SizedBox(height: AppSpacing.md),
          _DetailRow(label: loc.freightExchange_filterOrigin, value: load.origin),
          _DetailRow(
              label: loc.freightExchange_filterDestination,
              value: load.destination),
          if (load.cargoType != null)
            _DetailRow(
                label: loc.freightExchange_filterCargoType,
                value: load.cargoType!),
          if (load.price != null)
            _DetailRow(
              label: loc.freightExchange_price,
              value:
                  '${load.price!.toStringAsFixed(2)} ${load.currency ?? ''}',
            ),
          if (load.pickupDate != null)
            _DetailRow(
              label: loc.freightExchange_loadPickup,
              value: DateFormat.yMd().format(load.pickupDate!),
            ),
          if (load.deadlineDate != null)
            _DetailRow(
              label: loc.freightExchange_loadDeadline,
              value: DateFormat.yMd().format(load.deadlineDate!),
            ),
          if (load.weightKg != null)
            _DetailRow(
              label: loc.freightExchange_loadWeight,
              value: '${load.weightKg!.toStringAsFixed(0)} kg',
            ),
          if (load.distanceKm != null)
            _DetailRow(
              label: loc.freightExchange_loadDistance,
              value: '${load.distanceKm} km',
            ),
          const SizedBox(height: AppSpacing.lg),
          AppButton.primary(
            label: loc.freightExchange_import,
            onPressed: onImport,
          ),
          const SizedBox(height: AppSpacing.sm),
          AppButton.secondary(
            label: loc.freightExchange_evaluate,
            onPressed: onEvaluate,
          ),
        ],
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final String label;
  final String value;

  const _DetailRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '$label: ',
            style: AppTypography.bodySmall
                .copyWith(color: AppColors.textSecondary),
          ),
          Expanded(
            child: Text(
              value,
              style: AppTypography.bodyMedium,
            ),
          ),
        ],
      ),
    );
  }
}
