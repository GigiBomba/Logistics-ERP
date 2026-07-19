import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../shared/widgets/empty_state.dart';

/// Placeholder for Phase 2/3 features not yet built.
class UnderConstructionScreen extends StatelessWidget {
  final String featureName;
  const UnderConstructionScreen(this.featureName, {super.key});

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    return Scaffold(
      appBar: AppBar(title: Text(featureName)),
      body: Center(
        child: EmptyState(
          icon: const Icon(LucideIcons.construction, size: 56, color: AppColors.neutralText),
          title: loc.general_comingSoon,
          subtitle: loc.general_comingSoonDescription,
        ),
      ),
    );
  }
}
