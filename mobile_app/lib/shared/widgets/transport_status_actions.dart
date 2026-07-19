import 'package:flutter/material.dart';
import '../../core/i18n/app_localizations.dart';
import 'app_button.dart';

/// Available status transition for a transport.
class StatusAction {
  final String status;
  final String label;
  final bool isPrimary;

  const StatusAction({
    required this.status,
    required this.label,
    required this.isPrimary,
  });
}

/// Helper providing available next-status actions for a given transport status.
abstract final class TransportStatusActions {
  TransportStatusActions._();

  /// Returns available status transitions from [currentStatus].
  ///
  /// Each entry contains the target status key, a display label, and whether
  /// the action should be rendered as a primary (filled) button.
  static List<StatusAction> getNextActions(String currentStatus) {
    switch (currentStatus) {
      case 'planned':
        return [
          const StatusAction(status: 'loading', label: 'Start Loading', isPrimary: true),
        ];
      case 'loading':
        return [
          const StatusAction(status: 'in_transit', label: 'Depart', isPrimary: true),
        ];
      case 'in_transit':
        return [
          const StatusAction(status: 'delivered', label: 'Mark Delivered', isPrimary: true),
          const StatusAction(status: 'overdue', label: 'Report Delay', isPrimary: false),
        ];
      default:
        return [];
    }
  }

  /// Returns true if [status] is a terminal state with no further transitions.
  static bool isTerminal(String status) =>
      status == 'delivered' || status == 'cancelled';
}

/// A column of status action buttons for a transport.
///
/// Renders primary/secondary [AppButton]s for each available [StatusAction]
/// from [TransportStatusActions.getNextActions]. Shows a "No actions" label
/// when no transitions are available for the current status.
class TransportStatusButtons extends StatelessWidget {
  final String currentStatus;
  final Set<String> loadingStatuses;
  final bool isOffline;
  final ValueChanged<String> onStatusUpdate;
  final String Function(String statusKey)? labelResolver;
  final String? noActionsText;

  const TransportStatusButtons({
    super.key,
    required this.currentStatus,
    this.loadingStatuses = const {},
    this.isOffline = false,
    required this.onStatusUpdate,
    this.labelResolver,
    this.noActionsText,
  });

  @override
  Widget build(BuildContext context) {
    if (TransportStatusActions.isTerminal(currentStatus)) {
      return const SizedBox.shrink();
    }

    final actions = TransportStatusActions.getNextActions(currentStatus);

    if (actions.isEmpty) {
      return Text(
        noActionsText ?? 'No actions available for "$currentStatus" status.',
        style: TextStyle(
          fontSize: 12,
          color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
        ),
      );
    }

    return Column(
      children: actions.map((action) {
        final label = labelResolver != null
            ? labelResolver!(action.status)
            : action.label;
        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: action.isPrimary
              ? AppButton.primary(
                  key: ValueKey('status_${action.status}'),
                  label: label,
                  isLoading: loadingStatuses.contains(action.status),
                  onPressed: loadingStatuses.contains(action.status)
                      ? null
                      : () => onStatusUpdate(action.status),
                )
              : AppButton.secondary(
                  key: ValueKey('status_${action.status}'),
                  label: label,
                  isLoading: loadingStatuses.contains(action.status),
                  onPressed: loadingStatuses.contains(action.status)
                      ? null
                      : () => onStatusUpdate(action.status),
                ),
        );
      }).toList(),
    );
  }
}
