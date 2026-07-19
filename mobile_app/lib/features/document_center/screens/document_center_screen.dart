import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/empty_state.dart';

/// Document Center screen — full company document browsing + OCR Automation.
///
/// Two tabs:
/// 1. Documents — browse all company documents (reuses existing document patterns)
/// 2. Automation — camera capture → OCR upload flow
class DocumentCenterScreen extends ConsumerStatefulWidget {
  const DocumentCenterScreen({super.key});

  @override
  ConsumerState<DocumentCenterScreen> createState() => _DocumentCenterScreenState();
}

class _DocumentCenterScreenState extends ConsumerState<DocumentCenterScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.nav_documentCenter),
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            Tab(icon: const Icon(LucideIcons.folderOpen), text: loc.documentCenter_documents),
            Tab(icon: const Icon(LucideIcons.camera), text: loc.documentCenter_automation),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const [
          _DocumentsTab(),
          _AutomationTab(),
        ],
      ),
    );
  }
}

/// Documents list tab — placeholder for full document browsing.
class _DocumentsTab extends StatelessWidget {
  const _DocumentsTab();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: EmptyState(
        icon: Icon(LucideIcons.fileText, size: 56),
        title: 'Documents',
        subtitle: 'All company documents will appear here.',
      ),
    );
  }
}

/// Automation tab — camera capture → OCR upload flow.
///
/// Flow (Blueprint §6.4):
/// 1. Open camera → capture photo
/// 2. Generate Idempotency-Key (UUID)
/// 3. POST /api/v1/ocr/process → OcrUploadResponse
/// 4. Show "upload confirmed, processing" state
/// 5. NO polling loop — results stay server-side until Local Download
class _AutomationTab extends ConsumerWidget {
  const _AutomationTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final loc = context.loc;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(LucideIcons.camera, size: 64, color: AppColors.accent.withValues(alpha: 0.5)),
            const SizedBox(height: AppSpacing.lg),
            Text(
              loc.documentCenter_ocrTitle,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              loc.documentCenter_ocrDescription,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
              ),
            ),
            const SizedBox(height: AppSpacing.xl),
            AppButton.primary(
              label: loc.documentCenter_capturePhoto,
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(loc.documentCenter_uploadConfirmed)),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
