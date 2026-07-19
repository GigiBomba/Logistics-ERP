import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/network/api_client.dart';
import 'package:operion_mobile/core/network/endpoints/auth_endpoints.dart';
import 'package:operion_mobile/core/network/endpoints/device_endpoints.dart';
import 'package:operion_mobile/core/network/endpoints/dispatcher_endpoints.dart';
import 'package:operion_mobile/core/network/endpoints/document_endpoints.dart';
import 'package:operion_mobile/core/network/endpoints/driver_endpoints.dart';
import 'package:operion_mobile/core/network/endpoints/sync_endpoints.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Mock interceptor that captures request details and resolves instantly
// ─────────────────────────────────────────────────────────────────────────────

class _MockInterceptor extends Interceptor {
  final Map<String, dynamic> Function()? responseDataFn;
  final void Function(RequestOptions)? onRequestCallback;
  final int statusCode;

  _MockInterceptor({
    this.responseDataFn,
    this.onRequestCallback,
    this.statusCode = 200,
  });

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    onRequestCallback?.call(options);
    handler.resolve(Response(
      requestOptions: options,
      data: responseDataFn?.call() ?? {'status': 'ok'},
      statusCode: statusCode,
    ));
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper – builds an ApiClient whose Dio has only our mock interceptor
// ─────────────────────────────────────────────────────────────────────────────

ApiClient _createMockClient({
  required void Function(RequestOptions) onRequest,
  Map<String, dynamic>? responseData,
  int statusCode = 200,
}) {
  final client = ApiClient.create(
    baseUrl: 'https://api.test.com',
    getAccessToken: () async => null,
    getRefreshToken: () async => null,
    saveTokens: (_, __) async {},
    clearTokens: () async {},
  );
  // Remove all production interceptors (logging + auth) and add our mock
  client.dio.interceptors
    ..clear()
    ..add(_MockInterceptor(
      onRequestCallback: onRequest,
      responseDataFn: () => responseData ?? {'status': 'ok'},
      statusCode: statusCode,
    ));
  return client;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  // ===========================================================================
  // AuthEndpoints
  // ===========================================================================
  group('AuthEndpoints', () {
    late AuthEndpoints endpoints;
    late RequestOptions captured;

    setUp(() {
      captured = RequestOptions(path: '');
    });

    test('login sends POST to /api/v1/auth/token with form-urlencoded body', () async {
      endpoints = AuthEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.login('user@test.com', 's3cret');

      expect(captured.method, equals('POST'));
      expect(captured.path, equals('/api/v1/auth/token'));
      expect(captured.data, isA<Map>());
      expect((captured.data as Map)['username'], equals('user@test.com'));
      expect((captured.data as Map)['password'], equals('s3cret'));
      expect((captured.data as Map)['device_id'], isNull);
      expect(captured.contentType, equals(Headers.formUrlEncodedContentType));
    });

    test('login allows special characters in credentials', () async {
      endpoints = AuthEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.login('admin+test@example.com', 'p@ss!w#rd');

      expect((captured.data as Map)['username'], equals('admin+test@example.com'));
      expect((captured.data as Map)['password'], equals('p@ss!w#rd'));
    });

    test('login includes device_id when provided', () async {
      endpoints = AuthEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.login('user@test.com', 's3cret', deviceId: 'my-device-uuid');

      expect((captured.data as Map)['device_id'], equals('my-device-uuid'));
      expect(captured.contentType, equals(Headers.formUrlEncodedContentType));
    });

    test('login ignores empty device_id string', () async {
      endpoints = AuthEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.login('user@test.com', 's3cret', deviceId: '');

      expect((captured.data as Map)['device_id'], isNull);
    });

    test('refreshToken sends POST to /api/v1/auth/refresh with JSON body', () async {
      endpoints = AuthEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.refreshToken('rtoken123');

      expect(captured.method, equals('POST'));
      expect(captured.path, equals('/api/v1/auth/refresh'));
      expect(captured.data, isA<Map>());
      expect((captured.data as Map)['refresh_token'], equals('rtoken123'));
    });

    test('logout sends POST to /api/v1/auth/logout', () async {
      endpoints = AuthEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.logout();

      expect(captured.method, equals('POST'));
      expect(captured.path, equals('/api/v1/auth/logout'));
    });

    test('getMe sends GET to /auth/me', () async {
      endpoints = AuthEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.getMe();

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/auth/me'));
    });

    test('refreshToken response is parsed correctly', () async {
      endpoints = AuthEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
        responseData: <String, dynamic>{'access_token': 'new_at', 'refresh_token': 'new_rt'},
      ));

      final response = await endpoints.refreshToken('rtoken123');

      expect(response.statusCode, equals(200));
      expect(response.data['access_token'], equals('new_at'));
      expect(response.data['refresh_token'], equals('new_rt'));
    });

    test('registerDevice sends POST to /mobile/devices/register with device_id and platform', () async {
      endpoints = AuthEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.registerDevice(
        deviceId: 'dev-123',
        platform: 'android',
      );

      expect(captured.method, equals('POST'));
      expect(captured.path, equals('/api/v1/mobile/devices/register'));
      expect(captured.data, isA<Map>());
      expect((captured.data as Map)['device_id'], equals('dev-123'));
      expect((captured.data as Map)['platform'], equals('android'));
      expect((captured.data as Map)['device_name'], isNull);
      expect((captured.data as Map)['token'], isNull);
    });

    test('registerDevice includes optional device_name and fcm_token', () async {
      endpoints = AuthEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.registerDevice(
        deviceId: 'dev-456',
        platform: 'ios',
        deviceName: 'iPhone 15',
        fcmToken: 'fcm-abc-123',
      );

      expect((captured.data as Map)['device_id'], equals('dev-456'));
      expect((captured.data as Map)['platform'], equals('ios'));
      expect((captured.data as Map)['device_name'], equals('iPhone 15'));
      expect((captured.data as Map)['token'], equals('fcm-abc-123'));
    });
  });

  // ===========================================================================
  // DriverEndpoints
  // ===========================================================================
  group('DriverEndpoints', () {
    late DriverEndpoints endpoints;
    late RequestOptions captured;

    setUp(() {
      captured = RequestOptions(path: '');
    });

    test('getMyDay sends GET to /mobile/driver/my-day', () async {
      endpoints = DriverEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.getMyDay();

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/mobile/driver/my-day'));
    });

    test('getTransports sends GET to /mobile/driver/transports', () async {
      endpoints = DriverEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.getTransports();

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/mobile/driver/transports'));
    });

    test('getTransport sends GET with id in path', () async {
      endpoints = DriverEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.getTransport('42');

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/mobile/driver/transports/42'));
    });

    test('getTransport works with string identifiers containing letters', () async {
      endpoints = DriverEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.getTransport('T-100');

      expect(captured.path, equals('/api/v1/mobile/driver/transports/T-100'));
    });

    test('updateStatus sends PATCH with transport id and status in body', () async {
      endpoints = DriverEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.updateStatus('42', 'delivered');

      expect(captured.method, equals('PATCH'));
      expect(captured.path, equals('/api/v1/mobile/transports/42/status'));
      expect(captured.data, isA<Map>());
      expect((captured.data as Map)['status'], equals('delivered'));
    });

    test('updateStatus supports different status values', () async {
      endpoints = DriverEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.updateStatus('7', 'in_progress');

      expect((captured.data as Map)['status'], equals('in_progress'));
      expect(captured.path, equals('/api/v1/mobile/transports/7/status'));
    });

    test('getVehicle sends GET to /mobile/driver/vehicle', () async {
      endpoints = DriverEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.getVehicle();

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/mobile/driver/vehicle'));
    });

    test('getMessages sends GET to /mobile/messages', () async {
      endpoints = DriverEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.getMessages();

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/mobile/messages'));
    });

    test('sendMessage sends POST with receiver_id and text', () async {
      endpoints = DriverEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.sendMessage('5', 'hello');

      expect(captured.method, equals('POST'));
      expect(captured.path, equals('/api/v1/mobile/messages'));
      expect(captured.data, isA<Map>());
      expect((captured.data as Map)['receiver_id'], equals('5'));
      expect((captured.data as Map)['text'], equals('hello'));
    });

    test('sendMessage works with numeric receiver id and long text', () async {
      endpoints = DriverEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.sendMessage('999', 'Arriving in 10 minutes with the shipment.');

      expect((captured.data as Map)['receiver_id'], equals('999'));
      expect((captured.data as Map)['text'], equals('Arriving in 10 minutes with the shipment.'));
    });
  });

  // ===========================================================================
  // DispatcherEndpoints
  // ===========================================================================
  group('DispatcherEndpoints', () {
    late DispatcherEndpoints endpoints;
    late RequestOptions captured;

    setUp(() {
      captured = RequestOptions(path: '');
    });

    test('getOverview sends GET to /mobile/dispatcher/overview', () async {
      endpoints = DispatcherEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.getOverview();

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/mobile/dispatcher/overview'));
    });

    test('getFleet sends GET to /mobile/dispatcher/fleet', () async {
      endpoints = DispatcherEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.getFleet();

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/mobile/dispatcher/fleet'));
    });

    test('getJobs sends GET to /mobile/dispatcher/jobs', () async {
      endpoints = DispatcherEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.getJobs();

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/mobile/dispatcher/jobs'));
    });

    test('getDrivers sends GET to /mobile/dispatcher/drivers', () async {
      endpoints = DispatcherEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.getDrivers();

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/mobile/dispatcher/drivers'));
    });

    test('getAlerts sends GET to /mobile/dispatcher/alerts', () async {
      endpoints = DispatcherEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.getAlerts();

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/mobile/dispatcher/alerts'));
    });

    test('approveAction sends POST with id in path', () async {
      endpoints = DispatcherEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.approveAction('1');

      expect(captured.method, equals('POST'));
      expect(captured.path, equals('/api/v1/mobile/dispatcher/approvals/1/approve'));
    });

    test('approveAction works with different approval id', () async {
      endpoints = DispatcherEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.approveAction('42');

      expect(captured.path, equals('/api/v1/mobile/dispatcher/approvals/42/approve'));
    });

    test('rejectAction sends POST with reason in body', () async {
      endpoints = DispatcherEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.rejectAction('1', reason: 'Incomplete paperwork');

      expect(captured.method, equals('POST'));
      expect(captured.path, equals('/api/v1/mobile/dispatcher/approvals/1/reject'));
      expect(captured.data, isA<Map>());
      expect((captured.data as Map)['reason'], equals('Incomplete paperwork'));
    });

    test('rejectAction sends null reason when not provided', () async {
      endpoints = DispatcherEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.rejectAction('1');

      expect(captured.method, equals('POST'));
      expect(captured.path, equals('/api/v1/mobile/dispatcher/approvals/1/reject'));
      expect(captured.data, isA<Map>());
      expect((captured.data as Map)['reason'], isNull);
    });

    test('reassignTransport sends POST with driver_id body', () async {
      endpoints = DispatcherEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.reassignTransport('10', '7');

      expect(captured.method, equals('POST'));
      expect(captured.path, equals('/api/v1/mobile/dispatcher/jobs/10/reassign'));
      expect(captured.data, isA<Map>());
      expect((captured.data as Map)['driver_id'], equals('7'));
    });

    test('reassignTransport works with different ids', () async {
      endpoints = DispatcherEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.reassignTransport('99', '15');

      expect(captured.path, equals('/api/v1/mobile/dispatcher/jobs/99/reassign'));
      expect((captured.data as Map)['driver_id'], equals('15'));
    });
  });

  // ===========================================================================
  // DocumentEndpoints
  // ===========================================================================
  group('DocumentEndpoints', () {
    late RequestOptions captured;
    late Directory tempDir;

    setUp(() {
      captured = RequestOptions(path: '');
      tempDir = Directory.systemTemp.createTempSync('document_test_');
    });

    tearDown(() {
      tempDir.deleteSync(recursive: true);
    });

    String _createTempFile(String name) {
      final file = File('${tempDir.path}/$name');
      file.writeAsBytesSync([0x89, 0x50, 0x4E, 0x47]); // minimal PNG header
      return file.path;
    }

    test('uploadDocument sends POST to /mobile/documents/upload with FormData', () async {
      final endpoints = DocumentEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.uploadDocument('42', 'pod', _createTempFile('signature.png'));

      expect(captured.method, equals('POST'));
      expect(captured.path, equals('/api/v1/mobile/documents/upload'));
      expect(captured.data, isA<FormData>());
      expect(captured.contentType, contains('multipart/form-data'));
    });

    test('uploadDocument FormData contains transport_id and document_type', () async {
      final endpoints = DocumentEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.uploadDocument('99', 'invoice', _createTempFile('invoice.pdf'));

      final formData = captured.data as FormData;
      expect(formData.fields.any((e) => e.key == 'transport_id' && e.value == '99'), isTrue);
      expect(formData.fields.any((e) => e.key == 'document_type' && e.value == 'invoice'), isTrue);
    });

    test('uploadDocument FormData contains file entry', () async {
      final endpoints = DocumentEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.uploadDocument('7', 'pod', _createTempFile('photo.jpg'));

      final formData = captured.data as FormData;
      expect(formData.files, hasLength(1));
      expect(formData.files.first.key, equals('file'));
      expect(formData.files.first.value, isA<MultipartFile>());
    });

    test('uploadDocument handles different document types', () async {
      final endpoints = DocumentEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.uploadDocument('100', 'damage_report', _createTempFile('damage.jpg'));

      final formData = captured.data as FormData;
      expect(formData.fields.any((e) => e.key == 'transport_id' && e.value == '100'), isTrue);
      expect(formData.fields.any((e) => e.key == 'document_type' && e.value == 'damage_report'), isTrue);
    });
  });

  // ===========================================================================
  // SyncEndpoints
  // ===========================================================================
  group('SyncEndpoints', () {
    late SyncEndpoints endpoints;
    late RequestOptions captured;

    setUp(() {
      captured = RequestOptions(path: '');
    });

    test('getDelta sends GET to /mobile/sync with since query parameter', () async {
      endpoints = SyncEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.getDelta('cursor123');

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/mobile/sync'));
      expect(captured.queryParameters, containsPair('since', 'cursor123'));
    });

    test('synEntity sends GET with entity query parameter', () async {
      endpoints = SyncEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.syncEntity('transport');

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/mobile/sync'));
      expect(captured.queryParameters, containsPair('entity', 'transport'));
      expect(captured.queryParameters, isNot(contains('since')));
    });

    test('syncEntity with cursor includes both entity and since', () async {
      endpoints = SyncEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.syncEntity('driver', cursor: 'abc');

      expect(captured.queryParameters, containsPair('entity', 'driver'));
      expect(captured.queryParameters, containsPair('since', 'abc'));
    });

    test('syncEntityFull sends GET with entity and full=true', () async {
      endpoints = SyncEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.syncEntityFull('transport');

      expect(captured.method, equals('GET'));
      expect(captured.path, equals('/api/v1/mobile/sync'));
      expect(captured.queryParameters, containsPair('entity', 'transport'));
      expect(captured.queryParameters, containsPair('full', 'true'));
    });

    test('getDelta response is returned correctly', () async {
      endpoints = SyncEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
        responseData: <String, dynamic>{'entities': <dynamic>[<String, dynamic>{'id': 1}], 'cursor': 'next_cursor'},
      ));

      final response = await endpoints.getDelta('cursor123');

      expect(response.data['cursor'], equals('next_cursor'));
      expect(response.data['entities'], hasLength(1));
    });
  });

  // ===========================================================================
  // DeviceEndpoints
  // ===========================================================================
  group('DeviceEndpoints', () {
    late DeviceEndpoints endpoints;
    late RequestOptions captured;

    setUp(() {
      captured = RequestOptions(path: '');
    });

    test('registerDevice sends POST to /mobile/devices/register with token and platform', () async {
      endpoints = DeviceEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.registerDevice('fcm-token-abc', 'android');

      expect(captured.method, equals('POST'));
      expect(captured.path, equals('/api/v1/mobile/devices/register'));
      expect(captured.data, isA<Map>());
      expect((captured.data as Map)['token'], equals('fcm-token-abc'));
      expect((captured.data as Map)['platform'], equals('android'));
    });

    test('registerDevice works with iOS platform', () async {
      endpoints = DeviceEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.registerDevice('ios-token-xyz', 'ios');

      expect((captured.data as Map)['token'], equals('ios-token-xyz'));
      expect((captured.data as Map)['platform'], equals('ios'));
    });

    test('registerDevice includes device_id and device_name when provided', () async {
      endpoints = DeviceEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.registerDevice(
        'fcm-token-abc',
        'android',
        deviceId: 'dev-789',
        deviceName: 'Pixel 8',
      );

      expect((captured.data as Map)['token'], equals('fcm-token-abc'));
      expect((captured.data as Map)['platform'], equals('android'));
      expect((captured.data as Map)['device_id'], equals('dev-789'));
      expect((captured.data as Map)['device_name'], equals('Pixel 8'));
    });

    test('registerDevice omits device_id and device_name when not provided', () async {
      endpoints = DeviceEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.registerDevice('fcm-token-abc', 'android');

      expect((captured.data as Map)['token'], equals('fcm-token-abc'));
      expect((captured.data as Map)['platform'], equals('android'));
      expect((captured.data as Map)['device_id'], isNull);
      expect((captured.data as Map)['device_name'], isNull);
    });

    test('unregisterDevice sends DELETE to /mobile/devices/register', () async {
      endpoints = DeviceEndpoints(_createMockClient(
        onRequest: (opts) {
          captured = opts;
        },
      ));

      await endpoints.unregisterDevice();

      expect(captured.method, equals('DELETE'));
      expect(captured.path, equals('/api/v1/mobile/devices/register'));
    });
  });

  // ===========================================================================
  // Cross-cutting concerns – Error handling
  // ===========================================================================
  group('Error handling', () {
    test('endpoint propagates non-200 status codes', () async {
      final endpoints = DriverEndpoints(_createMockClient(
        onRequest: (_) {},
        statusCode: 400,
        responseData: <String, dynamic>{'error': 'bad request'},
      ));

      final response = await endpoints.getMyDay();

      expect(response.statusCode, equals(400));
      expect(response.data['error'], equals('bad request'));
    });

    test('endpoint propagates server error status', () async {
      final endpoints = DispatcherEndpoints(_createMockClient(
        onRequest: (_) {},
        statusCode: 500,
        responseData: <String, dynamic>{'message': 'Internal server error'},
      ));

      final response = await endpoints.getFleet();

      expect(response.statusCode, equals(500));
      expect(response.data['message'], equals('Internal server error'));
    });
  });
}
