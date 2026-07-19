import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/models/message.dart';
import '../../../shared/widgets/empty_state.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import 'message_chat_screen.dart';
import 'message_providers.dart';

/// Displays a list of message threads grouped by sender.
///
/// Each thread card shows the sender name, a preview of the most recent
/// message, a relative timestamp, and a blue unread dot when the thread
/// contains unread messages. Tapping a thread navigates to
/// [MessageChatScreen] for that conversation.
///
/// States:
/// - **Loading**: shimmer placeholder cards (5 items).
/// - **Error**: centered error icon with message and retry button.
/// - **Empty**: [EmptyState] with a message icon and "No messages" text.
/// - **Data**: scrollable list of thread cards, sorted by most recent
///   message (newest first).
class MessageListScreen extends ConsumerWidget {
  const MessageListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final messagesAsync = ref.watch(messagesProvider);
    final loc = context.loc;

    return Scaffold(
      appBar: AppBar(title: Text(loc.nav_messages)),
      body: messagesAsync.when(
        loading: _buildShimmerLoading,
        error: (error, _) => _buildError(context, ref, error, loc),
        data: (messages) => _buildMessageList(context, ref, messages, loc),
      ),
    );
  }

  /// Builds a list of 5 shimmer card placeholders.
  Widget _buildShimmerLoading() {
    return ListView.builder(
      itemCount: 5,
      itemBuilder: (_, __) => const ShimmerCard(),
    );
  }

  /// Builds a centered error state with a retry button.
  Widget _buildError(
    BuildContext context,
    WidgetRef ref,
    Object error,
    AppLocalizations loc,
  ) {
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
              error.toString(),
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.textSecondaryDark,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.lg),
            ElevatedButton.icon(
              onPressed: () => ref.invalidate(messagesProvider),
              icon: const Icon(Icons.refresh),
              label: Text(loc.general_retry),
            ),
          ],
        ),
      ),
    );
  }

  /// Builds the threaded message list or an empty state.
  Widget _buildMessageList(
    BuildContext context,
    WidgetRef ref,
    List<Message> messages,
    AppLocalizations loc,
  ) {
    if (messages.isEmpty) {
      return EmptyState(
        icon: const Icon(Icons.message_outlined),
        title: loc.message_noMessages,
      );
    }

    // Group messages by sender to form threads.
    final threads = _groupBySender(messages);
    // Sort threads by the most recent message timestamp (newest first).
    final sortedThreads = _sortThreads(threads);

    return ListView.separated(
      padding: const EdgeInsets.all(AppSpacing.lg),
      itemCount: sortedThreads.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, index) {
        final entry = sortedThreads[index];
        final threadMessages = entry.value;

        // Most recent message in this thread.
        final lastMessage = threadMessages.reduce(
          (a, b) => a.timestamp.isAfter(b.timestamp) ? a : b,
        );

        final hasUnread = threadMessages.any((m) => !m.isRead);

        return _ThreadCard(
          senderName: lastMessage.senderName,
          lastMessage: lastMessage.text,
          timestamp: lastMessage.timestamp,
          hasUnread: hasUnread,
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute<void>(
                builder: (_) => MessageChatScreen(
                  threadId: lastMessage.senderId,
                  senderName: lastMessage.senderName,
                ),
              ),
            );
          },
        );
      },
    );
  }

  /// Groups messages by their [Message.senderId].
  Map<String, List<Message>> _groupBySender(List<Message> messages) {
    final grouped = <String, List<Message>>{};
    for (final msg in messages) {
      grouped.putIfAbsent(msg.senderId, () => []).add(msg);
    }
    return grouped;
  }

  /// Sorts thread entries so the thread with the newest message appears
  /// first.
  List<MapEntry<String, List<Message>>> _sortThreads(
    Map<String, List<Message>> threads,
  ) {
    final entries = threads.entries.toList();
    entries.sort((a, b) {
      final aLatest = a.value
          .reduce((x, y) => x.timestamp.isAfter(y.timestamp) ? x : y)
          .timestamp;
      final bLatest = b.value
          .reduce((x, y) => x.timestamp.isAfter(y.timestamp) ? x : y)
          .timestamp;
      return bLatest.compareTo(aLatest);
    });
    return entries;
  }
}

// ---------------------------------------------------------------------------
// _ThreadCard
// ---------------------------------------------------------------------------

/// A single message thread preview card.
///
/// Displays the sender name (bold), last message preview (gray, single
/// line), relative timestamp, and a blue unread indicator dot.
class _ThreadCard extends StatelessWidget {
  const _ThreadCard({
    required this.senderName,
    required this.lastMessage,
    required this.timestamp,
    required this.hasUnread,
    required this.onTap,
  });

  final String senderName;
  final String lastMessage;
  final DateTime timestamp;
  final bool hasUnread;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      margin: EdgeInsets.zero,
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.lgAll,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Avatar with first letter
              CircleAvatar(
                radius: 22,
                backgroundColor: AppColors.accent.withValues(alpha: 0.15),
                child: Text(
                  senderName.isNotEmpty
                      ? senderName[0].toUpperCase()
                      : '?',
                  style: TextStyle(
                    color: AppColors.accent,
                    fontWeight: FontWeight.w600,
                    fontSize: 16,
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Sender name row with unread dot and timestamp
                    Row(
                      children: [
                        Text(
                          senderName,
                          style: theme.textTheme.titleSmall?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        if (hasUnread) ...[
                          const SizedBox(width: AppSpacing.sm),
                          Container(
                            width: 8,
                            height: 8,
                            decoration: const BoxDecoration(
                              color: AppColors.info,
                              shape: BoxShape.circle,
                            ),
                          ),
                        ],
                        const Spacer(),
                        Text(
                          _formatRelativeTime(context, timestamp),
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: AppColors.textSecondaryDark,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    // Last message preview
                    Text(
                      lastMessage,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: AppColors.textSecondaryDark,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Formats [timestamp] as a relative string (e.g. "2 min ago", "ieri",
  /// "12/07/2026").
  String _formatRelativeTime(BuildContext context, DateTime timestamp) {
    final now = DateTime.now();
    final diff = now.difference(timestamp);
    final loc = context.loc;

    if (diff.isNegative) return loc.general_justNow;
    if (diff.inSeconds < 60) return loc.general_justNow;
    if (diff.inMinutes < 60) {
      return loc.general_minAgo.replaceAll('{count}', diff.inMinutes.toString());
    }
    if (diff.inHours < 2) return loc.general_hourAgo;
    if (diff.inHours < 24) {
      return loc.general_hoursAgo.replaceAll('{count}', diff.inHours.toString());
    }
    // Yesterday
    final yesterday = DateTime(now.year, now.month, now.day - 1);
    final msgDate = DateTime(timestamp.year, timestamp.month, timestamp.day);
    if (msgDate == yesterday) return 'ieri';
    // Older: show date
    return '${timestamp.day.toString().padLeft(2, '0')}/'
        '${timestamp.month.toString().padLeft(2, '0')}/'
        '${timestamp.year}';
  }
}
