import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:io';

import 'package:path_provider/path_provider.dart';

/// Lightweight local database wrapper.
///
/// Uses in-memory maps persisted as JSON files on disk.  This is a temporary
/// implementation until Isar schemas are code-generated from the domain models.
///
/// TODO: Replace the file-based approach with proper Isar collections once the
///       following are in place:
///       - Annotated model classes with `@collection`
///       - `isar_generator` run via `build_runner`
///       - Generated `.isar.dart` files imported here
///
/// Usage:
/// ```dart
/// final db = LocalDatabase();
/// await db.initialize();
/// await db.cacheData('transports', 'tr-42', {'id': 'tr-42', 'status': 'active'});
/// final data = await db.getCachedData('transports', 'tr-42');
/// print(data?['status']); // 'active'
/// await db.close();
/// ```
class LocalDatabase {
  Directory? _baseDir;

  /// In-memory cache: `collection -> key -> JSON string`.
  final _cache = <String, Map<String, String>>{};

  /// Whether the database has been initialised.
  bool _initialized = false;

  // ── Initialisation ────────────────────────────

  /// Open (or create) the local database directory.
  ///
  /// The database files are stored in the app's documents directory under
  /// `operion_cache/`.
  Future<void> initialize() async {
    if (_initialized) return;

    final appDir = await getApplicationDocumentsDirectory();
    _baseDir = Directory('${appDir.path}/operion_cache');
    if (!await _baseDir!.exists()) {
      await _baseDir!.create(recursive: true);
    }

    _initialized = true;
    developer.log('LocalDatabase initialised at ${_baseDir!.path}',
        name: 'LocalDatabase');
  }

  // ── Transport caching ─────────────────────────

  /// Replace the entire transports cache with the provided list.
  Future<void> cacheTransports(List<Map<String, dynamic>> transports) async {
    await clearCollection('transports');
    for (final t in transports) {
      final id = t['id']?.toString() ?? _fallbackId(t);
      await cacheData('transports', id, t);
    }
  }

  /// Retrieve all cached transports as a list of maps.
  Future<List<Map<String, dynamic>>> getCachedTransports() async {
    final items = await _getAllFromCollection('transports');
    return items;
  }

  // ── Generic key-value cache ───────────────────

  /// Store a single [data] map under [key] within [collection].
  Future<void> cacheData(
    String collection,
    String key,
    Map<String, dynamic> data,
  ) async {
    _ensureCollection(collection);
    _cache[collection]![key] = jsonEncode(data);
    await _persistCollection(collection);
  }

  /// Retrieve a cached map by [collection] and [key], or `null` if absent.
  Future<Map<String, dynamic>?> getCachedData(
    String collection,
    String key,
  ) async {
    _ensureCollection(collection);
    final raw = _cache[collection]![key];
    if (raw == null) return null;
    final decoded = jsonDecode(raw);
    return decoded is Map<String, dynamic> ? decoded : null;
  }

  /// Remove all entries belonging to [collection].
  Future<void> clearCollection(String collection) async {
    _cache.remove(collection);
    final file = _collectionFile(collection);
    if (await file.exists()) {
      await file.delete();
    }
  }

  // ── Namespaced key-value helpers ──────────────

  /// Reads the JSON-decoded value stored at [key] within [namespace].
  ///
  /// The [namespace] maps to an internal collection. Returns `null` when the
  /// key does not exist.
  ///
  /// This is the equivalent of `getCachedData(namespace, key)` but accepts
  /// arbitrary JSON values (lists, primitives, etc.) not only maps.
  Future<dynamic> read(String key, {String namespace = 'default'}) async {
    await _loadCollection(namespace);
    _ensureCollection(namespace);
    final raw = _cache[namespace]![key];
    if (raw == null) return null;
    try {
      return jsonDecode(raw);
    } catch (e) {
      developer.log(
        'LocalDatabase.read: $namespace:$key → $e',
        name: 'LocalDatabase',
      );
      return null;
    }
  }

  /// Stores a JSON-encodable [value] at [key] within [namespace].
  ///
  /// The [namespace] maps to an internal collection. Any prior value at the
  /// same key is overwritten.
  Future<void> write(
    String key,
    dynamic value, {
    String namespace = 'default',
  }) async {
    await _loadCollection(namespace);
    _ensureCollection(namespace);
    _cache[namespace]![key] = jsonEncode(value);
    await _persistCollection(namespace);
  }

  /// Deletes the entry at [key] within [namespace].
  ///
  /// No-op if the key does not exist.
  Future<void> delete(String key, {String namespace = 'default'}) async {
    await _loadCollection(namespace);
    if (_cache.containsKey(namespace)) {
      _cache[namespace]!.remove(key);
      await _persistCollection(namespace);
    }
  }

  /// Returns all keys within [namespace] that start with [prefix].
  ///
  /// Useful for enumerating stored items in a namespaced scope.
  Future<List<String>> keysWithPrefix(
    String prefix, {
    String namespace = 'default',
  }) async {
    await _loadCollection(namespace);
    _ensureCollection(namespace);
    return _cache[namespace]!
        .keys
        .where((k) => k.startsWith(prefix))
        .toList();
  }

  /// Removes every entry within [namespace] whose key starts with [prefix].
  Future<void> deleteAllWithPrefix(
    String prefix, {
    String namespace = 'default',
  }) async {
    await _loadCollection(namespace);
    if (!_cache.containsKey(namespace)) return;
    _cache[namespace]!.removeWhere((k, _) => k.startsWith(prefix));
    await _persistCollection(namespace);
  }

  /// Close the database and release resources.
  Future<void> close() async {
    _cache.clear();
    _initialized = false;
    developer.log('LocalDatabase closed', name: 'LocalDatabase');
  }

  // ── Internal helpers ──────────────────────────

  void _ensureCollection(String collection) {
    _cache.putIfAbsent(collection, () => <String, String>{});
  }

  File _collectionFile(String collection) {
    if (_baseDir == null) {
      throw StateError(
        'LocalDatabase not initialised. Call initialize() first.',
      );
    }
    return File('${_baseDir!.path}/$collection.json');
  }

  /// Persist a single collection's in-memory map to disk.
  Future<void> _persistCollection(String collection) async {
    final entries = _cache[collection];
    if (entries == null) return;
    final file = _collectionFile(collection);
    await file.writeAsString(jsonEncode(entries));
  }

  /// Load a collection from disk into the in-memory cache.
  Future<void> _loadCollection(String collection) async {
    final file = _collectionFile(collection);
    if (await file.exists()) {
      try {
        final raw = await file.readAsString();
        final decoded = jsonDecode(raw) as Map<String, dynamic>;
        _cache[collection] = decoded.cast<String, String>();
      } catch (e) {
        developer.log(
          'LocalDatabase: failed to load collection "$collection" – $e',
          name: 'LocalDatabase',
        );
        _cache[collection] = <String, String>{};
      }
    } else {
      _cache[collection] = <String, String>{};
    }
  }

  /// Retrieve all decoded maps from a collection.
  Future<List<Map<String, dynamic>>> _getAllFromCollection(
    String collection,
  ) async {
    await _loadCollection(collection);
    final entries = _cache[collection] ?? <String, String>{};
    return entries.values
        .map((raw) => jsonDecode(raw) as Map<String, dynamic>)
        .toList();
  }

  String _fallbackId(Map<String, dynamic> map) {
    return map.hashCode.toString();
  }
}
