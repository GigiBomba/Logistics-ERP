import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/i18n/app_localizations.dart';
import '../../../core/network/endpoints/driver_endpoints.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/models/message.dart';
import '../../../shared/widgets/empty_state.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import '../home/driver_providers.dart';
import 'message_providers.dart';

/// Chat screen for a specific conversation thread.
///
/// Displays messages between the current driver and the contact identified
/// by [threadId]. The AppBar shows the [senderName] and a back button.
///
/// Messages sent by the current user appear as right-aligned indigo bubbles
/// with white text. Received messages appear as left-aligned gray bubbles
/// with dark text. Each bubble includes a timestamp (HH:mm) below it.
///
/// A fixed input bar at the bottom allows the user to type and send
/// messages. Messages are added optimistically to the list and the send
/// request is dispatched to the API.
class MessageChatScreen extends ConsumerStatefulWidget {
  /// The identifier of the conversation partner (senderId / receiverId).
  final String threadId;

  /// The display name shown in the AppBar.
  final String senderName;

  const MessageChatScreen({
    super.key,
    required this.threadId,
    required this.senderName,
  });

  @override
  ConsumerState<MessageChatScreen> createState() => _MessageChatScreenState();
}

class _MessageChatScreenState extends ConsumerState<MessageChatScreen> {
  final _messageController = TextEditingController();
  final _scrollController = ScrollController();

  /// Locally-managed message list (includes API data + optimistic sends).
  List<Message> _messages = [];

  /// Whether the initial load is in progress.
  bool _isLoading = true;

  /// Error message from the initial load, if any.
  String? _error;

  /// The current user's ID, used to determine which messages are "mine".
  String? _currentUserId;

  @override
  void initState() {
    super.initState();
    _loadMessages();
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  /// Fetches messages from the API and filters them to this thread.
  Future<void> _loadMessages() async {
    try {
      final endpoints = ref.read(driverEndpointsProvider);
      final user = ref.read(currentUserProvider);
      final response = await endpoints.getMessages();
      final raw = response.data;
      final list = raw is List ? raw : (raw is Map ? (raw['records'] ?? raw['data'] ?? []) as List : []);
      final allMessages = list
          .map((json) => Message.fromJson(json as Map<String, dynamic>))
          .toList();

      if (!mounted) return;

      setState(() {
        _messages = allMessages
            .where((m) =>
                m.senderId == widget.threadId ||
                m.receiverId == widget.threadId)
            .toList();
        _currentUserId = user?.id;
        _isLoading = false;
      });

      // Scroll to the bottom after messages load.
      WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToNewest());
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  /// Scrolls the message list to the most recent (newest) message.
  void _scrollToNewest() {
    if (_messages.isNotEmpty && _scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.minScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  /// Sends a message to the thread partner.
  ///
  /// Adds the message optimistically to the local list, clears the input
  /// field, and dispatches the API call. On failure the error is silently
  /// caught (the message remains in the list with its optimistic state).
  Future<void> _sendMessage() async {
    final text = _messageController.text.trim();
    if (text.isEmpty) return;

    final user = ref.read(currentUserProvider);
    final userId = user?.id ?? '';
    final userName = user?.fullName ?? '';

    // Build an optimistic message with a temporary ID.
    final optimistic = Message(
      id: '__optimistic_${DateTime.now().millisecondsSinceEpoch}',
      senderId: userId,
      senderName: userName,
      receiverId: widget.threadId,
      text: text,
      timestamp: DateTime.now(),
      isRead: false,
    );

    setState(() {
      _messages = [optimistic, ..._messages];
      _messageController.clear();
    });

    // Scroll to show the new message.
    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToNewest());

    // Mark sending state.
    ref.read(messageSendingProvider.notifier).state = true;

    try {
      final endpoints = ref.read(driverEndpointsProvider);
      await endpoints.sendMessage(widget.threadId, text);
      // Success — the optimistic message stays in the list. In a full
      // implementation we would replace the temporary ID with the real one
      // from the server response.
    } catch (_) {
      // Send failed — mark the message with a failed flag and notify the
      // user so they can retry.
      if (!mounted) return;
      setState(() {
        _messages = _messages.map((m) {
          if (m.id == optimistic.id) {
            return m.copyWith(hasFailed: true);
          }
          return m;
        }).toList();
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text('Message failed to send. Try again.'),
          backgroundColor: AppColors.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } finally {
      ref.read(messageSendingProvider.notifier).state = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final isSending = ref.watch(messageSendingProvider);
    final isOffline = ref.watch(isOfflineProvider);
    final loc = context.loc;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.senderName),
      ),
      body: Column(
        children: [
          // Offline indicator
          if (isOffline)
            Container(
              width: double.infinity,
              color: Colors.amber.shade700,
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.lg,
                vertical: AppSpacing.sm,
              ),
              child: Text(
                loc.general_offline,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                ),
                textAlign: TextAlign.center,
              ),
            ),

          // Message list
          Expanded(child: _buildMessages(loc, theme)),

          // Message input bar
          _buildInputBar(loc, isSending),
        ],
      ),
    );
  }

  /// Builds the message list area, handling loading / error / data states.
  Widget _buildMessages(AppLocalizations loc, ThemeData theme) {
    if (_isLoading) {
      return ListView.builder(
        itemCount: 6,
        itemBuilder: (_, __) => const ShimmerLoader(
          child: Padding(
            padding: EdgeInsets.symmetric(
              horizontal: AppSpacing.lg,
              vertical: AppSpacing.sm,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _ShimmerBubble(width: 0.7),
                SizedBox(height: AppSpacing.xs),
                _ShimmerBubble(width: 0.4),
              ],
            ),
          ),
        ),
      );
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xxl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48, color: AppColors.error),
              const SizedBox(height: AppSpacing.lg),
              Text(
                loc.general_error,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                _error!,
                style: const TextStyle(
                  fontSize: 13,
                  color: AppColors.textSecondaryDark,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.lg),
              ElevatedButton.icon(
                onPressed: () {
                  setState(() {
                    _isLoading = true;
                    _error = null;
                  });
                  _loadMessages();
                },
                icon: const Icon(Icons.refresh),
                label: Text(loc.general_retry),
              ),
            ],
          ),
        ),
      );
    }

    if (_messages.isEmpty) {
      return EmptyState(
        icon: const Icon(Icons.chat_outlined),
        title: loc.message_noMessages,
      );
    }

    // Sort messages newest-first (most recent at top).
    final sorted = List<Message>.from(_messages)
      ..sort((a, b) => b.timestamp.compareTo(a.timestamp));

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.sm,
      ),
      itemCount: sorted.length,
      itemBuilder: (context, index) {
        final message = sorted[index];
        final isMine = message.senderId == _currentUserId;
        return _MessageBubble(
          message: message,
          isMine: isMine,
          theme: theme,
        );
      },
    );
  }

  /// Builds the fixed input bar at the bottom of the screen.
  Widget _buildInputBar(AppLocalizations loc, bool isSending) {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.08),
            blurRadius: 4,
            offset: const Offset(0, -1),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.sm,
          ),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _messageController,
                  textInputAction: TextInputAction.send,
                  maxLines: null,
                  decoration: InputDecoration(
                    hintText: loc.message_typeMessage,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(AppRadius.xl),
                      borderSide: BorderSide.none,
                    ),
                    filled: true,
                    fillColor: Theme.of(context)
                        .colorScheme
                        .surfaceContainerHighest
                        .withValues(alpha: 0.5),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.lg,
                      vertical: AppSpacing.sm,
                    ),
                  ),
                  onSubmitted: (_) => _sendMessage(),
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              IconButton(
                onPressed: isSending ? null : _sendMessage,
                icon: isSending
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.send_rounded),
                style: IconButton.styleFrom(
                  backgroundColor: AppColors.accent,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(AppRadius.xl),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// _MessageBubble
// ---------------------------------------------------------------------------

/// A single chat message bubble.
///
/// - **Sent by the current user**: right-aligned, indigo background, white
///   text, with a double-check (read) indicator.
/// - **Received**: left-aligned, gray background, dark text.
///
/// Below each bubble the timestamp (HH:mm) is displayed.
class _MessageBubble extends StatelessWidget {
  const _MessageBubble({
    required this.message,
    required this.isMine,
    required this.theme,
  });

  final Message message;
  final bool isMine;
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final timeStr = _formatTime(message.timestamp);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      child: Column(
        crossAxisAlignment:
            isMine ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          // Bubble
          Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.75,
            ),
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.sm,
            ),
            decoration: BoxDecoration(
              color: isMine ? AppColors.accent : AppColors.neutralSubtle,
              borderRadius: BorderRadius.only(
                topLeft: const Radius.circular(AppRadius.lg),
                topRight: const Radius.circular(AppRadius.lg),
                bottomLeft: Radius.circular(
                  isMine ? AppRadius.lg : AppRadius.sm,
                ),
                bottomRight: Radius.circular(
                  isMine ? AppRadius.sm : AppRadius.lg,
                ),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  message.text,
                  style: TextStyle(
                    color: isMine ? Colors.white : theme.colorScheme.onSurface,
                    fontSize: 15,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                // Timestamp + read indicator + failed indicator row
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      timeStr,
                      style: TextStyle(
                        color: isMine
                            ? Colors.white.withValues(alpha: 0.7)
                            : AppColors.textSecondaryDark,
                        fontSize: 10,
                      ),
                    ),
                    if (message.hasFailed) ...[
                      const SizedBox(width: 4),
                      const Icon(
                        Icons.warning_amber_rounded,
                        size: 14,
                        color: AppColors.error,
                      ),
                    ] else if (isMine) ...[
                      const SizedBox(width: 4),
                      Icon(
                        message.isRead
                            ? Icons.done_all_rounded
                            : Icons.done_rounded,
                        size: 14,
                        color: isMine
                            ? Colors.white.withValues(alpha: 0.7)
                            : AppColors.textSecondaryDark,
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Formats [timestamp] as HH:mm.
  String _formatTime(DateTime timestamp) {
    final hour = timestamp.hour.toString().padLeft(2, '0');
    final minute = timestamp.minute.toString().padLeft(2, '0');
    return '$hour:$minute';
  }
}

// ---------------------------------------------------------------------------
// _ShimmerBubble
// ---------------------------------------------------------------------------

/// A small shimmer placeholder line used in the chat loading state.
class _ShimmerBubble extends StatelessWidget {
  const _ShimmerBubble({this.width = 0.6});

  final double width;

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      widthFactor: width,
      child: Container(
        height: 14,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(AppRadius.sm),
        ),
      ),
    );
  }
}
