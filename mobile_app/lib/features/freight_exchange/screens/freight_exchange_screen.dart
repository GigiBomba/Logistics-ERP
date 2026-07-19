import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_text_field.dart';
import '../../../shared/widgets/empty_state.dart';

/// Freight Exchange screen — browse and accept external loads.
///
/// Consumes the provider-agnostic backend endpoint.
/// TIMOCOM is the first adapter; no TIMOCOM-specific field names in Flutter models.
class FreightExchangeScreen extends ConsumerStatefulWidget {
  const FreightExchangeScreen({super.key});

  @override
  ConsumerState<FreightExchangeScreen> createState() => _FreightExchangeScreenState();
}

class _FreightExchangeScreenState extends ConsumerState<FreightExchangeScreen> {
  final _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;

    return Scaffold(
      appBar: AppBar(title: Text(loc.nav_freightExchange)),
      body: Column(
        children: [
          // Search/filter bar
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: AppTextField(
              controller: _searchController,
              hintText: loc.freightExchange_searchHint,
              prefixIcon: const Icon(LucideIcons.search, size: 20),
            ),
          ),

          // Load list
          Expanded(
            child: Center(
              child: EmptyState(
                icon: const Icon(LucideIcons.search, size: 56),
                title: loc.freightExchange_empty,
                subtitle: loc.freightExchange_emptyHint,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
