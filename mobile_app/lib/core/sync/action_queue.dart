import 'dart:async';
import 'dart:developer' as developer;

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../storage/local_db.dart';

// ── Data models ───────────────────────────────────────────────────────

/// A single action queued for later replay when the device comes back online.
///
/// Each action carries an [id] (UUID) that doubles as an idempotency key so
/// the server can safely de-duplicate replays.
class QueuedAction {
  /// Idempotency key (UUID v4).
  final String id;

  /// API endpoint path, e.g. `/transports/42/status`.
  final String endpoint;

  /// HTTP method: `GET`, `POST`, `PATCH`, `DELETE`.
  final String method;

  /// Optional JSON-serialisable payload.
  final Map<String, dynamic>? data;

  /// When the action was first enqueued (UTC).
  final DateTime createdAt;

  /// How many times this action has been retried so far.
  final int retryCount;

  const QueuedAction({
    required this.id,
    required this.endpoint,
    required this.method,
    this.data,
    required this.createdAt,
    this.retryCount = 0,
  });

  /// Creates a copy with an incremented [retryCount].
  QueuedAction copyWith({int? retryCount}) {
    return QueuedAction(
      id: id,
      endpoint: endpoint,
      method: method,
      data: data,
      createdAt: createdAt,
      retryCount: retryCount ?? this.retryCount,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'endpoint': endpoint,
        'method': method,
        'data': data,
        'createdAt': createdAt.toIso8601String(),
        'retryCount': retryCount,
      };

  factory QueuedAction.fromJson(Map<String, dynamic> json) => QueuedAction(
        id: json['id'] as String,
        endpoint: json['endpoint'] as String,
        method: json['method'] as String,
        data: json['data'] is Map<String, dynamic>
            ? json['data'] as Map<String, dynamic>
            : null,
        createdAt: DateTime.parse(json['createdAt'] as String),
        retryCount: json['retryCount'] as int? ?? 0,
      );

  @override
  String toString() =>
      'QueuedAction(id: $id, $method $endpoint, retry: $retryCount)';
}

/// Observable state of the [ActionQueue].
class ActionQueueState {
  /// Number of actions currently waiting to be replayed.
  final int pendingCount;

  /// Whether the queue is currently replaying actions.
  final bool isReplaying;

  /// The last error that occurred during replay, if any.
  final String? lastError;

  const ActionQueueState({
    this.pendingCount = 0,
    this.isReplaying = false,
    this.lastError,
  });

  ActionQueueState copyWith({
    int? pendingCount,
    bool? isReplaying,
    String? lastError,
  }) {
    return ActionQueueState(
      pendingCount: pendingCount ?? this.pendingCount,
      isReplaying: isReplaying ?? this.isReplaying,
      lastError: lastError,
    );
  }

  @override
  String toString() =>
      'ActionQueueState(pending: $pendingCount, replaying: $isReplaying, error: $lastError)';
}

// ── Action queue ──────────────────────────────────────────────────────

/// Thread-safe offline action queue that persists pending operations to
/// [LocalDatabase] and replays them in FIFO order when connectivity returns.
///
/// Usage:
/// ```dart
/// final queue = ActionQueue(db);
/// await queue.initialize();
/// final actionId = await queue.enqueue('/transports/42/status', 'PATCH',
///     data: {'status': 'delivered'});
///
/// // Later, when online:
/// await queue.replayAll((action) => apiClient.patch(action.endpoint,
///     data: action.data));
/// ```
class ActionQueue {
  final LocalDatabase _db;

  /// Namespace used inside [LocalDatabase] for queued actions.
  static const String _namespace = 'action_queue';

  /// In-memory list of pending actions (FIFO order).
  final List<QueuedAction> _pending = [];

  final StreamController<ActionQueueState> _stateController =
      StreamController<ActionQueueState>.broadcast();

  bool _isReplaying = false;

  /// Broadcast stream that emits the latest [ActionQueueState] whenever the
  /// queue changes (enqueue, dequeue, replay start/end, error).
  Stream<ActionQueueState> get state => _stateController.stream;

  /// Number of actions currently queued.
  int get pendingCount => _pending.length;

  ActionQueue(this._db);

  /// Loads pending actions from persistent storage.
  ///
  /// Must be called once before using the queue.
  Future<void> initialize() async {
    try {
      // Remove any stale isReplaying flag from a previous crash.
      await _db.write('_meta_is_replaying', false, namespace: _namespace);

      final keys = await _db.keysWithPrefix('action_', namespace: _namespace);
      final actions = <QueuedAction>[];

      for (final key in keys) {
        final raw = await _db.read(key, namespace: _namespace);
        if (raw != null) {
          if (raw is Map<String, dynamic>) {
            actions.add(QueuedAction.fromJson(raw));
          } else {
            developer.log('Skipping corrupt action entry: $key', name: 'ActionQueue');
          }
        }
      }

      // Sort by creation time (oldest first) so we replay in FIFO order.
      actions.sort((a, b) => a.createdAt.compareTo(b.createdAt));
      _pending
        ..clear()
        ..addAll(actions);

      _emitState();
      developer.log(
        'ActionQueue: loaded ${_pending.length} pending action(s)',
        name: 'ActionQueue',
      );
    } catch (e) {
      developer.log(
        'ActionQueue.initialize: $e',
        name: 'ActionQueue',
      );
    }
  }

  /// Adds a new action to the queue and persists it.
  ///
  /// Returns the generated UUID (idempotency key).
  Future<String> enqueue(
    String endpoint,
    String method, {
    Map<String, dynamic>? data,
  }) async {
    final id = const Uuid().v4();
    final action = QueuedAction(
      id: id,
      endpoint: endpoint,
      method: method,
      data: data,
      createdAt: DateTime.now().toUtc(),
    );

    _pending.add(action);
    await _persistAction(action);
    _emitState();

    developer.log('ActionQueue: enqueued $action', name: 'ActionQueue');
    return id;
  }

  /// Removes a completed (or cancelled) action from the queue and persistent
  /// storage.
  Future<void> dequeue(String id) async {
    _pending.removeWhere((a) => a.id == id);
    await _db.delete('action_$id', namespace: _namespace);
    _emitState();
  }

  /// Replays every pending action in FIFO order using [executor].
  ///
  /// The [executor] callback receives each [QueuedAction] and must return a
  /// `Future` that completes when the HTTP call finishes (successfully or
  /// with a terminal failure).
  ///
  /// - On success the action is dequeued.
  /// - On a non-recoverable error (e.g. 409 Conflict, 404) the action is
  ///   dequeued and the error is surfaced via the state stream.
  /// - On a transient error (e.g. network timeout) the action is **not**
  ///   dequeued and will be retried on the next replay cycle.
  ///
  /// Returns the number of actions that were successfully replayed.
  Future<int> replayAll(
    Future<dynamic> Function(QueuedAction action) executor,
  ) async {
    if (_isReplaying) return 0;

    _isReplaying = true;
    await _db.write('_meta_is_replaying', true, namespace: _namespace);
    _emitState();

    var successCount = 0;
    // Work on a copy so concurrent enqueues do not interfere.
    final snapshot = List<QueuedAction>.from(_pending);

    for (final action in snapshot) {
      try {
        await executor(action);
        await dequeue(action.id);
        successCount++;
      } on ReplayPermanentFailure catch (e) {
        developer.log(
          'ActionQueue: permanent failure for $action → ${e.message}',
          name: 'ActionQueue',
        );
        await dequeue(action.id);
        _emitError(e.message);
      } catch (e) {
        // Transient failure – keep in queue, update retry count.
        final updated = action.copyWith(retryCount: action.retryCount + 1);
        final index = _pending.indexWhere((a) => a.id == action.id);
        if (index != -1) {
          _pending[index] = updated;
          await _persistAction(updated);
        }
        developer.log(
          'ActionQueue: transient failure for $action → $e',
          name: 'ActionQueue',
        );
        continue; // Skip failed action, continue with remaining.
      }
    }

    _isReplaying = false;
    await _db.write('_meta_is_replaying', false, namespace: _namespace);
    _emitState();

    return successCount;
  }

  /// Removes all pending actions without replaying them.
  Future<void> clear() async {
    _pending.clear();
    await _db.deleteAllWithPrefix('action_', namespace: _namespace);
    _emitState();
  }

  /// Frees resources held by the stream controller.
  void dispose() {
    _stateController.close();
  }

  // ── Persistence helpers ────────────────────────────────────────────

  Future<void> _persistAction(QueuedAction action) async {
    await _db.write(
      'action_${action.id}',
      action.toJson(),
      namespace: _namespace,
    );
  }

  void _emitState() {
    _stateController.add(ActionQueueState(
      pendingCount: _pending.length,
      isReplaying: _isReplaying,
    ));
  }

  void _emitError(String error) {
    _stateController.add(ActionQueueState(
      pendingCount: _pending.length,
      isReplaying: _isReplaying,
      lastError: error,
    ));
  }
}

/// Thrown by an [ActionQueue.replayAll] executor to signal a permanent
/// failure that should dequeue the action without retrying.
class ReplayPermanentFailure implements Exception {
  final String message;
  const ReplayPermanentFailure(this.message);

  @override
  String toString() => 'ReplayPermanentFailure: $message';
}

// ── Riverpod provider ─────────────────────────────────────────────────

/// Provides the singleton [ActionQueue] wired to the default [LocalDatabase].
final actionQueueProvider = Provider<ActionQueue>((ref) {
  final db = ref.watch(localDatabaseProvider);
  final queue = ActionQueue(db);
  ref.onDispose(() => queue.dispose());
  return queue;
});

/// Placeholder provider – override in your app with the real [LocalDatabase].
final localDatabaseProvider = Provider<LocalDatabase>((ref) {
  return LocalDatabase();
});
