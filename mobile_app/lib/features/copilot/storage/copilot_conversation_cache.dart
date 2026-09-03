/// Offline cache for Co-Pilot conversation history (§32.3).
///
/// The integration doc (§32.3) originally promised an "Isar-backed" cache, but
/// Isar is not a project dependency (and adding it means a codegen step +
/// native plugin for a read-only cache). To keep the dependency surface as
/// light as possible this implementation reuses the app's existing
/// [LocalDatabase] JSON store (path_provider backed) — the same storage the
/// transports cache and `ActionQueue` already use, under the `copilot`
/// namespace.
///
/// ## Scope — read-only results only
///
/// Only read-only endpoint results are cached:
/// - the `listConversations` response (conversation list), and
/// - the `getConversation` response (message history for one conversation).
///
/// Nothing user-authored or stateful is ever stored here, and the cache is
/// never written from optimistic UI.
///
/// ## Safety rules
///
/// - Every cached entry carries an explicit `isOffline` / `isReadOnly` flag so
///   cached results can never be presented as fresh server data.
/// - Entries expire after [ttl] (default 7 days).
/// - The per-conversation store is bounded to [maxConversations] entries;
///   the oldest are evicted first.
library;

import '../../../core/storage/local_db.dart';

/// A cached snapshot of a read-only Co-Pilot result.
///
/// [data] holds either a `listConversations` response map or a
/// `getConversation` response map, exactly as the backend returned it.
///
/// [isOffline] and [isReadOnly] are always `true` for entries read out of the
/// cache — they exist so callers can prove (and display) that they are not
/// showing fresh server data.
class CachedCopilotConversation {
  /// The raw read-only payload from the backend.
  final Map<String, dynamic> data;

  /// When this snapshot was cached.
  final DateTime cachedAt;

  /// Always `true` for cache entries.
  final bool isOffline;

  /// Always `true` — history is never mutable client-side.
  final bool isReadOnly;

  const CachedCopilotConversation({
    required this.data,
    required this.cachedAt,
    this.isOffline = true,
    this.isReadOnly = true,
  });

  /// Whether this snapshot is older than [ttl] at time [now].
  bool isExpired(DateTime now, Duration ttl) =>
      now.difference(cachedAt) > ttl;

  factory CachedCopilotConversation.fromJson(Map<String, dynamic> json) {
    final data = json['data'];
    final cachedAt = DateTime.tryParse(json['cached_at'] as String? ?? '');
    return CachedCopilotConversation(
      data: data is Map<String, dynamic> ? data : <String, dynamic>{},
      cachedAt: cachedAt ?? DateTime.now(),
      isOffline: json['is_offline'] as bool? ?? true,
      isReadOnly: json['is_read_only'] as bool? ?? true,
    );
  }

  Map<String, dynamic> toJson() => {
        'data': data,
        'cached_at': cachedAt.toIso8601String(),
        'is_offline': isOffline,
        'is_read_only': isReadOnly,
      };
}

/// Persists read-only Co-Pilot conversation history inside the shared
/// [LocalDatabase] under the `copilot` namespace.
///
/// Keys:
/// - `conversations`            → latest `listConversations` snapshot
/// - `conversation:<id>`        → `getConversation` snapshot per conversation
class CopilotConversationCache {
  /// Namespace used inside [LocalDatabase].
  static const String namespace = 'copilot';

  static const String _conversationsKey = 'conversations';
  static const String _conversationPrefix = 'conversation:';

  /// How long a snapshot stays valid before it is considered stale.
  static const Duration defaultTtl = Duration(days: 7);

  /// Maximum number of per-conversation snapshots kept on disk.
  static const int defaultMaxConversations = 50;

  final LocalDatabase _db;
  final Duration ttl;
  final int maxConversations;

  CopilotConversationCache(
    this._db, {
    this.ttl = defaultTtl,
    this.maxConversations = defaultMaxConversations,
  });

  // ── Conversation list ──────────────────────────────────────────────

  /// Caches the `listConversations` response [data].
  Future<void> cacheConversations(Map<String, dynamic> data) async {
    await _db.write(
      _conversationsKey,
      CachedCopilotConversation(data: data, cachedAt: DateTime.now()).toJson(),
      namespace: namespace,
    );
    await _trim();
  }

  /// Returns the cached conversation list, or `null` when absent/expired.
  Future<CachedCopilotConversation?> readCachedConversations() async {
    final raw = await _db.read(_conversationsKey, namespace: namespace);
    return _resolve(raw);
  }

  // ── Single conversation (message history) ──────────────────────────

  /// Caches the `getConversation` response [data] for [conversationId].
  Future<void> cacheConversation(
    String conversationId,
    Map<String, dynamic> data,
  ) async {
    await _db.write(
      '$_conversationPrefix$conversationId',
      CachedCopilotConversation(data: data, cachedAt: DateTime.now()).toJson(),
      namespace: namespace,
    );
    await _trim();
  }

  /// Returns the cached history for [conversationId], or `null` when
  /// absent/expired.
  Future<CachedCopilotConversation?> readCachedConversation(
    String conversationId,
  ) async {
    final raw = await _db.read(
      '$_conversationPrefix$conversationId',
      namespace: namespace,
    );
    return _resolve(raw);
  }

  // ── Maintenance ────────────────────────────────────────────────────

  /// Removes every cached Co-Pilot snapshot.
  Future<void> clear() async {
    await _db.deleteAllWithPrefix('', namespace: namespace);
  }

  /// Enforces [maxConversations] by evicting the oldest snapshots first.
  Future<void> _trim() async {
    final keys = await _db.keysWithPrefix(
      _conversationPrefix,
      namespace: namespace,
    );
    if (keys.length <= maxConversations) return;

    final entries = <({String key, DateTime cachedAt})>[];
    for (final key in keys) {
      final raw = await _db.read(key, namespace: namespace);
      if (raw is Map<String, dynamic>) {
        entries.add(
          (
            key: key,
            cachedAt: CachedCopilotConversation.fromJson(raw).cachedAt,
          ),
        );
      }
    }
    entries.sort((a, b) => a.cachedAt.compareTo(b.cachedAt));

    final excess = entries.length - maxConversations;
    for (final entry in entries.take(excess)) {
      await _db.delete(entry.key, namespace: namespace);
    }
  }

  CachedCopilotConversation? _resolve(dynamic raw) {
    if (raw is! Map<String, dynamic>) return null;
    final cached = CachedCopilotConversation.fromJson(raw);
    if (cached.isExpired(DateTime.now(), ttl)) return null;
    return cached;
  }
}