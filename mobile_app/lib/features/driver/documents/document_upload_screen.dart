import 'dart:async';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:path_provider/path_provider.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/i18n/app_localizations.dart';
import '../../../core/network/api_client.dart';
import '../../../core/sync/action_queue.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import 'ocr_result_card.dart';

/// A [ConsumerStatefulWidget] that guides the driver through document type
/// selection, image capture/gallery pick, preview, and upload with progress
/// feedback.
///
/// Usage:
/// ```dart
/// Navigator.push(
///   context,
///   MaterialPageRoute(
///     builder: (_) => DocumentUploadScreen(transportId: '...'),
///   ),
/// );
/// ```
class DocumentUploadScreen extends ConsumerStatefulWidget {
  const DocumentUploadScreen({
    super.key,
    required this.transportId,
  });

  /// The transport this document is associated with.
  final String transportId;

  @override
  ConsumerState<DocumentUploadScreen> createState() =>
      _DocumentUploadScreenState();
}

/// Possible steps in the document upload flow.
enum _UploadStep { selectType, captureMethod, preview, uploading, done, error }

/// Document type definition used for the selection grid.
class _DocTypeOption {
  final String type;
  final IconData icon;
  final String label;

  const _DocTypeOption({
    required this.type,
    required this.icon,
    required this.label,
  });
}

class _DocumentUploadScreenState
    extends ConsumerState<DocumentUploadScreen> {
  static const _docTypes = [
    _DocTypeOption(type: 'cmr', icon: LucideIcons.fileText, label: 'document_cmr'),
    _DocTypeOption(type: 'pod', icon: LucideIcons.clipboardCheck, label: 'document_pod'),
    _DocTypeOption(type: 'invoice', icon: LucideIcons.receipt, label: 'document_invoice'),
    _DocTypeOption(type: 'other', icon: LucideIcons.file, label: 'document_other'),
  ];

  final _picker = ImagePicker();

  _UploadStep _step = _UploadStep.selectType;
  String? _selectedType;
  File? _imageFile;
  double _progress = 0.0;
  String? _errorMessage;

  // ── OCR polling state ───────────────────────────
  Timer? _ocrPollTimer;
  int _ocrPollAttempts = 0;
  static const int _maxOcrAttempts = 5;
  static const Duration _ocrPollInterval = Duration(seconds: 2);
  String? _documentId;
  Map<String, dynamic>? _ocrResult;
  bool _ocrProcessing = false;

  /// Resets the entire flow so the user can start over.
  void _reset() {
    _cancelOcrPolling();
    setState(() {
      _step = _UploadStep.selectType;
      _selectedType = null;
      _imageFile = null;
      _progress = 0.0;
      _errorMessage = null;
      _ocrResult = null;
      _documentId = null;
      _ocrProcessing = false;
    });
  }

  @override
  void dispose() {
    _cancelOcrPolling();
    super.dispose();
  }

  /// Cancels the OCR polling timer if active.
  void _cancelOcrPolling() {
    _ocrPollTimer?.cancel();
    _ocrPollTimer = null;
    _ocrPollAttempts = 0;
  }

  /// Polls the OCR status endpoint until results arrive or we time out.
  void _startOcrPolling(String documentId) {
    _cancelOcrPolling();
    _documentId = documentId;
    _ocrPollAttempts = 0;
    _ocrProcessing = true;

    _ocrPollTimer = Timer.periodic(_ocrPollInterval, (_) async {
      if (!mounted) return;

      _ocrPollAttempts++;
      try {
        final apiClient = ref.read(apiClientProvider);
        final response = await apiClient.get(
          '/api/v1/ocr/status/$documentId',
        );
        final data = response.data as Map<String, dynamic>?;

        if (data != null && data['status'] == 'completed' && data['result'] != null) {
          _cancelOcrPolling();
          if (mounted) {
            setState(() {
              _ocrResult = Map<String, dynamic>.from(data['result'] as Map);
              _ocrProcessing = false;
            });
          }
          return;
        }

        // If the result is available directly (data fields present alongside status).
        if (data != null &&
            data['status'] == 'completed' &&
            data.length > 1) {
          _cancelOcrPolling();
          if (mounted) {
            // Omit the status key from the extracted result.
            final result = Map<String, dynamic>.from(data)
              ..remove('status');
            setState(() {
              _ocrResult = result;
              _ocrProcessing = false;
            });
          }
          return;
        }

        // Timeout: max attempts reached.
        if (_ocrPollAttempts >= _maxOcrAttempts) {
          _cancelOcrPolling();
          if (mounted) {
            setState(() {
              _ocrResult = {'_failed': true};
              _ocrProcessing = false;
            });
          }
        }
      } catch (_) {
        // Swallow polling errors — server may still be processing.
        if (_ocrPollAttempts >= _maxOcrAttempts) {
          _cancelOcrPolling();
          if (mounted) {
            setState(() {
              _ocrResult = {'_failed': true};
              _ocrProcessing = false;
            });
          }
        }
      }
    });
  }

  /// Captures an image using the device camera.
  Future<void> _takePhoto() async {
    try {
      final xFile = await _picker.pickImage(
        source: ImageSource.camera,
        maxWidth: 2048,
        maxHeight: 2048,
        imageQuality: 85,
      );
      if (xFile != null) {
        setState(() {
          _imageFile = File(xFile.path);
          _step = _UploadStep.preview;
        });
      }
    } catch (e) {
      // Permission denied or camera unavailable.
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text(
              'Camera access denied. Please enable it in Settings.',
            ),
            backgroundColor: AppColors.warning,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  /// Picks an image from the device gallery.
  Future<void> _pickFromGallery() async {
    try {
      final xFile = await _picker.pickImage(
        source: ImageSource.gallery,
        maxWidth: 2048,
        maxHeight: 2048,
        imageQuality: 85,
      );
      if (xFile != null) {
        setState(() {
          _imageFile = File(xFile.path);
          _step = _UploadStep.preview;
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$e')),
        );
      }
    }
  }

  /// Uploads the captured image to the server.
  ///
  /// Uses Dio directly to report upload progress via [onSendProgress].
  /// If the device is offline, enqueues the action for later sync using
  /// [ActionQueue].
  Future<void> _uploadDocument() async {
    if (_imageFile == null || _selectedType == null) return;

    setState(() {
      _step = _UploadStep.uploading;
      _progress = 0.0;
      _errorMessage = null;
    });

    try {
      final apiClient = ref.read(apiClientProvider);
      final formData = FormData.fromMap({
        'transport_id': widget.transportId,
        'document_type': _selectedType,
        'file': await MultipartFile.fromFile(_imageFile!.path),
      });

      final response = await apiClient.dio.post(
        '/mobile/documents/upload',
        data: formData,
        options: Options(contentType: 'multipart/form-data'),
        onSendProgress: (sent, total) {
          if (!mounted) return;
          final progress = total > 0 ? sent / total : 0.0;
          setState(() => _progress = progress);
        },
      );

      if (mounted) {
        setState(() => _step = _UploadStep.done);

        // Extract document ID for OCR polling.
        final responseData = response.data;
        if (responseData is Map<String, dynamic>) {
          final docId = (responseData['id'] ?? responseData['document_id']) as String?;
          if (docId != null && docId.isNotEmpty) {
            _startOcrPolling(docId);
          }
        }
      }
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout) {
        // Offline — queue for later sync.
        await _queueForSync();
      } else {
        _handleUploadError(e.message ?? 'Upload failed');
      }
    } catch (e) {
      _handleUploadError(e.toString());
    }
  }

  /// Queues the document upload action for later sync when connectivity
  /// is restored.
  ///
  /// Copies the captured file to persistent storage so it survives
  /// temporary-file cleanup before the sync executes.
  Future<void> _queueForSync() async {
    try {
      // Copy the temp file to persistent documents directory.
      final docsDir = await getApplicationDocumentsDirectory();
      final persistentDir = Directory('${docsDir.path}/pending_uploads');
      if (!await persistentDir.exists()) {
        await persistentDir.create(recursive: true);
      }
      final timestamp = DateTime.now().millisecondsSinceEpoch;
      final persistentPath = '${persistentDir.path}/doc_$timestamp.jpg';
      if (_imageFile != null) {
        await _imageFile!.copy(persistentPath);
      }

      final queue = ref.read(actionQueueProvider);
      await queue.enqueue(
        '/mobile/documents/upload',
        'POST',
        data: {
          'transport_id': widget.transportId,
          'document_type': _selectedType,
          'file_path': persistentPath,
        },
      );
      if (mounted) {
        setState(() => _step = _UploadStep.done);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text(
              'Document queued for upload when connection is restored',
            ),
            backgroundColor: AppColors.warning,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (_) {
      _handleUploadError('Failed to queue for sync');
    }
  }

  /// Sets the error state with a descriptive message.
  void _handleUploadError(String message) {
    if (!mounted) return;
    setState(() {
      _step = _UploadStep.error;
      _errorMessage = message;
    });
  }

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.document_upload)),
      body: SafeArea(
        child: switch (_step) {
          _UploadStep.selectType => _buildTypeSelection(loc),
          _UploadStep.captureMethod => _buildCaptureMethod(loc),
          _UploadStep.preview => _buildPreview(loc),
          _UploadStep.uploading => _buildUploadProgress(loc),
          _UploadStep.done => _buildDone(loc),
          _UploadStep.error => _buildError(loc),
        },
      ),
    );
  }

  /// Step 1: Grid of document type cards.
  Widget _buildTypeSelection(AppLocalizations loc) {
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Select document type',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.lg),
          Expanded(
            child: GridView.builder(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                mainAxisSpacing: AppSpacing.md,
                crossAxisSpacing: AppSpacing.md,
                childAspectRatio: 1.1,
              ),
              itemCount: _docTypes.length,
              itemBuilder: (context, index) {
                final option = _docTypes[index];
                final isSelected = _selectedType == option.type;
                return _DocTypeCard(
                  icon: option.icon,
                  label: _localizedLabel(loc, option),
                  isSelected: isSelected,
                  onTap: () {
                    setState(() {
                      _selectedType = option.type;
                      _step = _UploadStep.captureMethod;
                    });
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  /// Maps the [_DocTypeOption.label] key to its localized string.
  String _localizedLabel(AppLocalizations loc, _DocTypeOption option) {
    return switch (option.type) {
      'cmr' => loc.document_cmr,
      'pod' => loc.document_pod,
      'invoice' => loc.document_invoice,
      _ => loc.document_other,
    };
  }

  /// Step 2: Choose capture method — camera or gallery.
  Widget _buildCaptureMethod(AppLocalizations loc) {
    final selectedDocType =
        _docTypes.firstWhere((d) => d.type == _selectedType);
    final selectedLabel = _localizedLabel(loc, selectedDocType);

    return Padding(
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        children: [
          const Spacer(flex: 2),
          Icon(
            LucideIcons.fileText,
            size: 72,
            color: Theme.of(context)
                .colorScheme
                .primary
                .withValues(alpha: 0.4),
          ),
          const SizedBox(height: AppSpacing.lg),
          Text(
            selectedLabel,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: AppSpacing.xxl),
          Row(
            children: [
              Expanded(
                child: AppButton.primary(
                  label: loc.document_capture,
                  icon: const Icon(LucideIcons.camera),
                  onPressed: _takePhoto,
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: AppButton.secondary(
                  label: loc.document_selectGallery,
                  icon: const Icon(LucideIcons.image),
                  onPressed: _pickFromGallery,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          TextButton(
            onPressed: () => setState(() => _step = _UploadStep.selectType),
            child: Text(loc.general_cancel),
          ),
          const Spacer(flex: 3),
        ],
      ),
    );
  }

  /// Step 3: Image preview with retake / confirm actions.
  Widget _buildPreview(AppLocalizations loc) {
    return Column(
      children: [
        Expanded(
          child: InteractiveViewer(
            child: Center(
              child: ClipRRect(
                borderRadius: AppRadius.xlAll,
                child: Image.file(
                  _imageFile!,
                  fit: BoxFit.contain,
                  width: double.infinity,
                ),
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: AppButton.secondary(
                      label: 'Retake',
                      icon: const Icon(LucideIcons.rotateCcw),
                      onPressed: () =>
                          setState(() => _step = _UploadStep.captureMethod),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: AppButton.primary(
                      label: loc.general_confirm,
                      icon: const Icon(LucideIcons.check),
                      onPressed: _uploadDocument,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }

  /// Step 4: Upload progress with a linear progress bar.
  Widget _buildUploadProgress(AppLocalizations loc) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              height: 64,
              width: 64,
              child: CircularProgressIndicator(
                value: _progress > 0 ? _progress : null,
                strokeWidth: 4,
              ),
            ),
            const SizedBox(height: AppSpacing.xxl),
            Text(
              loc.document_uploading,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (_progress > 0) ...[
              const SizedBox(height: AppSpacing.sm),
              Text(
                '${(_progress * 100).toInt()}%',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppColors.textSecondaryLight,
                    ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Step 5: Success state with a checkmark animation and optional OCR results.
  Widget _buildDone(AppLocalizations loc) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.xxl),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // ── Upload success icon ──────────────────
          Container(
            height: 80,
            width: 80,
            decoration: const BoxDecoration(
              color: AppColors.successSubtle,
              shape: BoxShape.circle,
            ),
            child: const Icon(
              LucideIcons.checkCircle,
              size: 48,
              color: AppColors.success,
            ),
          ),
          const SizedBox(height: AppSpacing.xxl),
          Text(
            loc.document_uploaded,
            style: Theme.of(context).textTheme.titleLarge,
          ),

          // ── OCR results / processing state ────────
          if (_ocrResult?['_failed'] == true)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.lg),
              child: AppCard(
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: Row(
                    children: [
                      const Icon(
                        LucideIcons.alertTriangle,
                        size: 20,
                        color: AppColors.warning,
                      ),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: Text(
                          'OCR could not complete. Results may appear later.',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            )
          else if (_ocrResult != null)
            OcrResultCard(
              ocrData: _ocrResult!,
              onConfirm: () {
                // Save the OCR data confirmation and close the screen.
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text('Saved'),
                    backgroundColor: AppColors.success,
                    behavior: SnackBarBehavior.floating,
                  ),
                );
                Navigator.pop(context);
              },
              onEdit: () {
                // Return to the previous screen with edit mode flag.
                Navigator.pop(context, {'editMode': true, 'ocrData': _ocrResult});
              },
            )
          else if (_ocrProcessing)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.lg),
              child: AppCard(
                child: Row(
                  children: [
                    const SizedBox(
                      height: 18,
                      width: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Text(
                        loc.ocr_processing,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                  ],
                ),
              ),
            ),

          const SizedBox(height: AppSpacing.xl),
          AppButton.primary(
            label: 'Upload Another',
            icon: const Icon(LucideIcons.plus),
            onPressed: _reset,
          ),
          const SizedBox(height: AppSpacing.md),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(loc.general_confirm),
          ),
        ],
      ),
    );
  }

  /// Error state with retry button.
  Widget _buildError(AppLocalizations loc) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              height: 80,
              width: 80,
              decoration: const BoxDecoration(
                color: AppColors.errorSubtle,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                LucideIcons.alertCircle,
                size: 48,
                color: AppColors.error,
              ),
            ),
            const SizedBox(height: AppSpacing.xxl),
            Text(
              loc.document_failed,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (_errorMessage != null) ...[
              const SizedBox(height: AppSpacing.sm),
              Text(
                _errorMessage!,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppColors.textSecondaryLight,
                    ),
              ),
            ],
            const SizedBox(height: AppSpacing.xl),
            AppButton.primary(
              label: loc.general_retry,
              icon: const Icon(LucideIcons.refreshCcw),
              onPressed: _uploadDocument,
            ),
            const SizedBox(height: AppSpacing.md),
            TextButton(
              onPressed: _reset,
              child: Text('Start over'),
            ),
          ],
        ),
      ),
    );
  }
}

/// A selectable card widget for each document type in the grid.
class _DocTypeCard extends StatelessWidget {
  const _DocTypeCard({
    required this.icon,
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final borderColor =
        isSelected ? theme.colorScheme.primary : Colors.transparent;

    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        decoration: BoxDecoration(
          color: isSelected
              ? theme.colorScheme.primaryContainer
              : theme.colorScheme.surfaceContainerHighest,
          borderRadius: AppRadius.xlAll,
          border: Border.all(
            color: borderColor,
            width: 2,
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              size: 36,
              color: isSelected
                  ? theme.colorScheme.primary
                  : theme.colorScheme.onSurface.withValues(alpha: 0.6),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              label,
              style: TextStyle(
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                color: isSelected
                    ? theme.colorScheme.primary
                    : theme.colorScheme.onSurface,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
