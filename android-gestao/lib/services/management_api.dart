import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

class ManagementApi {
  ManagementApi(this.origin) {
    if (origin.scheme != 'https' || origin.host.isEmpty || origin.userInfo.isNotEmpty) {
      throw ArgumentError('A API precisa usar uma origem HTTPS.');
    }
    _client.connectionTimeout = const Duration(seconds: 15);
  }

  final Uri origin;
  final _client = HttpClient();
  Cookie? _session;

  Future<({int tenantId, int userId, String role})> login(String store, String email, String password) async {
    _session = null;
    try {
      await _request('POST', '/api/admin/auth/login', body: {
        'tenant_slug': store,
        'email': email,
        'password': password,
      });
      final profile = await _request('GET', '/api/admin/auth/me') as Map<String, dynamic>;
      if (profile['email_verification_required'] == true &&
          profile['email_verified'] != true) {
        throw const ManagementApiError(412);
      }
      return (tenantId: profile['tenant_id'] as int, userId: profile['id'] as int, role: (profile['role'] as String).trim().toLowerCase());
    } catch (_) {
      _session = null;
      rethrow;
    }
  }

  Future<void> requestPasswordReset(String store, String email) async {
    await _request('POST', '/api/admin/auth/forgot-password',
        authenticated: false, body: {
          'tenant_slug': store.trim().toLowerCase(),
          'email': email.trim(),
        });
  }

  Uri? get onboardingUrl {
    final host = switch (origin.host) {
      'api.fomizero.com.br' => 'www.fomizero.com.br',
      'super-saas-delivery-production.up.railway.app' => 'meuburger.staging.fomizero.com.br',
      _ => null,
    };
    return host == null ? null : Uri.https(host, '/onboarding', {'source': 'gestao_android'});
  }

  Future<({List<Map<String, dynamic>> items, int total})> orders(
    int tenantId, {
    required int page,
    String customer = '',
    String number = '',
    String status = '',
  }) async {
    final query = Uri(queryParameters: {
      'page': '$page',
      'page_size': '8',
      if (customer.isNotEmpty) 'customer': customer,
      if (number.isNotEmpty) 'order_number': number,
      if (status.isNotEmpty) 'status': status,
    }).query;
    final data = await _request('GET', '/api/orders/$tenantId/search?$query')
        as Map<String, dynamic>;
    return (
      items: (data['items'] as List).cast<Map<String, dynamic>>(),
      total: data['total'] as int,
    );
  }

  Future<Map<String, dynamic>> orderSummary(int tenantId) async {
    final now = DateTime.now();
    final query = Uri(queryParameters: {
      'today': now.toIso8601String().split('T').first,
      'utc_offset_minutes': '${-now.timeZoneOffset.inMinutes}',
    }).query;
    final data = await _request('GET', '/api/orders/$tenantId/overview?$query')
        as Map<String, dynamic>;
    return data['summary'] as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> dashboard(DateTime start, DateTime end) async {
    String date(DateTime day) => day.toIso8601String().split('T').first;

    final first = DateTime.utc(start.year, start.month, start.day);
    final last = DateTime.utc(end.year, end.month, end.day);
    final days = last.difference(first).inDays + 1;
    final query = Uri(queryParameters: {
      'start_date': date(first),
      'end_date': date(last),
    }).query;
    final previousQuery = Uri(queryParameters: {
      'start_date': date(first.subtract(Duration(days: days))),
      'end_date': date(first.subtract(const Duration(days: 1))),
    }).query;

    final overview = await _request('GET', '/api/dashboard/overview?$query');
    final sections = await Future.wait([
      _dashboardSection('/api/dashboard/overview?$previousQuery'),
      _dashboardSection('/api/dashboard/timeseries?$query&bucket=day'),
      _dashboardSection('/api/dashboard/top-items?$query&limit=8'),
      _dashboardSection('/api/dashboard/recent-orders?$query&limit=8'),
    ]);
    return {
      'overview': overview,
      'previous': sections[0],
      'timeseries': sections[1]?['points'],
      'items': sections[2]?['items'],
      'orders': sections[3]?['orders'],
    };
  }

  Future<Map<String, dynamic>?> _dashboardSection(String path) async {
    try {
      return await _request('GET', path) as Map<String, dynamic>;
    } on ManagementApiError catch (error) {
      if (error.status == 401) rethrow;
      return null;
    } on IOException {
      return null;
    } on TimeoutException {
      return null;
    }
  }

  Future<List<Map<String, dynamic>>> kitchenOrders(String area) async {
    final query = Uri(queryParameters: {'area': area}).query;
    return (await _request('GET', '/api/kds/orders?$query') as List)
        .cast<Map<String, dynamic>>();
  }

  Future<void> advanceKitchenOrder(int orderId, String area, {required bool ready}) async {
    final query = Uri(queryParameters: {'area': area}).query;
    final action = ready ? 'ready' : 'start';
    await _request('POST', '/api/kds/orders/$orderId/$action?$query');
  }

  Future<({List<Map<String, dynamic>> categories, List<Map<String, dynamic>> items})> menu() async {
    final result = await Future.wait([
      _request('GET', '/api/admin/menu/categories'),
      _request('GET', '/api/admin/menu/items?include_inactive=true'),
    ]);
    return (
      categories: (result[0] as List).cast<Map<String, dynamic>>(),
      items: (result[1] as List).cast<Map<String, dynamic>>(),
    );
  }

  Future<({List<Map<String, dynamic>> items, List<Map<String, dynamic>> movements})>
      inventory(DateTime from, DateTime to) async {
    final query = Uri(queryParameters: {
      'de': from.toIso8601String().split('T').first,
      'para': to.toIso8601String().split('T').first,
    }).query;
    final data = await Future.wait([
      _request('GET', '/api/inventory/items'),
      _request('GET', '/api/inventory/movements?$query'),
    ]);
    return (
      items: (data[0] as List).cast<Map<String, dynamic>>(),
      movements: (data[1] as List).cast<Map<String, dynamic>>(),
    );
  }

  Future<({List<Map<String, dynamic>> items, int total})> customers(
    int page, String search,
  ) async {
    final query = Uri(queryParameters: {
      'page': '$page',
      'limit': '20',
      if (search.isNotEmpty) 'search': search,
    }).query;
    final data = await _request('GET', '/api/admin/customers?$query') as Map<String, dynamic>;
    return (
      items: (data['items'] as List).cast<Map<String, dynamic>>(),
      total: data['total'] as int,
    );
  }

  Future<Map<String, dynamic>> customer(int id) async =>
      await _request('GET', '/api/admin/customers/$id') as Map<String, dynamic>;

  String _periodQuery(DateTime from, DateTime to) => Uri(queryParameters: {
    'from': from.toIso8601String().split('T').first,
    'to': to.toIso8601String().split('T').first,
  }).query;

  Future<({Map<String, dynamic> summary, List<Map<String, dynamic>> movements})>
      finance(DateTime from, DateTime to) async {
    final query = _periodQuery(from, to);
    final data = await Future.wait([
      _request('GET', '/api/finance/cash/summary?$query'),
      _request('GET', '/api/finance/cash/movements?$query'),
    ]);
    return (
      summary: data[0] as Map<String, dynamic>,
      movements: (data[1] as List).cast<Map<String, dynamic>>(),
    );
  }

  Future<({Map<String, dynamic> summary, List<Map<String, dynamic>> items,
      List<Map<String, dynamic>> lowStock})> reports(DateTime from, DateTime to) async {
    final query = _periodQuery(from, to);
    final data = await Future.wait([
      _request('GET', '/api/reports/financial/summary?$query'),
      _request('GET', '/api/reports/sales/top-items?$query'),
      _request('GET', '/api/reports/inventory/low-stock?$query'),
    ]);
    List<Map<String, dynamic>> rows(Object? payload) {
      final value = payload is Map ? payload['items'] : payload;
      return (value as List).cast<Map<String, dynamic>>();
    }
    return (summary: data[0] as Map<String, dynamic>, items: rows(data[1]), lowStock: rows(data[2]));
  }

  Future<List<Map<String, dynamic>>> deliveries() async =>
      (await _request('GET', '/api/delivery/orders?status=READY,OUT_FOR_DELIVERY') as List)
          .cast<Map<String, dynamic>>();

  Future<void> advanceDelivery(int id, {required bool complete}) async {
    final action = complete ? 'complete-delivery' : 'start-delivery';
    await _request('PATCH', '/api/orders/$id/$action');
  }

  Future<List<Map<String, dynamic>>> deliveryUsers(int tenantId) async =>
      (await _request('GET', '/api/admin/$tenantId/delivery-users') as List)
          .cast<Map<String, dynamic>>();

  Future<List<Map<String, dynamic>>> adminUsers() async =>
      (await _request('GET', '/api/admin/users') as List).cast<Map<String, dynamic>>();

  Future<List<Map<String, dynamic>>> auditEvents(DateTime? from, DateTime? to) async {
    final query = Uri(queryParameters: {
      if (from != null) 'from': from.toUtc().toIso8601String(),
      if (to != null)
        'to': DateTime(to.year, to.month, to.day, 23, 59, 59, 999, 999).toUtc().toIso8601String(),
    }).query;
    return (await _request('GET', '/api/admin/audit?$query') as List)
        .cast<Map<String, dynamic>>();
  }

  Future<List<Map<String, dynamic>>> marketingEntries(String section) async {
    final result = await _request('GET', '/api/admin/marketing/$section');
    return result is List
        ? result.cast<Map<String, dynamic>>()
        : [result as Map<String, dynamic>];
  }

  Future<void> saveMarketing(String section, Map<String, Object?> body) async {
    await _request(
      section == 'loyalty' ? 'PUT' : 'POST',
      '/api/admin/marketing/$section',
      body: body,
    );
  }

  Future<Map<String, dynamic>> wazzaConnection() async =>
      await _request('GET', '/api/orders/wazza/requests/connection') as Map<String, dynamic>;

  Future<({List<Map<String, dynamic>> items, int? next})> wazzaRequests(int? before) async {
    final query = before == null ? '' : '?before=$before';
    final response = await _request('GET', '/api/orders/wazza/requests$query') as Map<String, dynamic>;
    return (items: (response['items'] as List).cast<Map<String, dynamic>>(), next: response['next'] as int?);
  }

  Future<void> decideWazzaRequest(int id, String action, String reason) async {
    await _request('POST', '/api/orders/wazza/requests/$id/decision',
      body: {'action': action, 'reason': reason});
  }

  Future<List<Map<String, dynamic>>> whatsappLogs(int tenantId) async {
    final rows = await _request('GET', '/api/admin/$tenantId/whatsapp/logs?limit=20') as List;
    return [
      for (final row in rows.cast<Map<String, dynamic>>())
        {'direction': row['direction'], 'status': row['status'], 'created_at': row['created_at']},
    ];
  }

  Future<Map<String, dynamic>> catalogAppearance() async =>
      await _request('GET', '/api/appearance') as Map<String, dynamic>;

  Future<void> updateCatalogAppearance(Map<String, Object?> colorsAndLayout) async {
    await _request('PUT', '/api/appearance', body: colorsAndLayout);
  }

  Future<Map<String, dynamic>> catalogPreview(String store) async {
    final query = Uri(queryParameters: {'slug': store}).query;
    return await _request('GET', '/public/menu?$query', authenticated: false) as Map<String, dynamic>;
  }

  Future<void> createCategory(int tenantId, String name) async {
    await _request('POST', '/api/admin/menu/categories', body: {
      'tenant_id': tenantId, 'name': name, 'active': true,
    });
  }

  Future<void> updateCategory(int id, String name, bool active) async {
    await _request('PUT', '/api/admin/menu/categories/$id',
      body: {'name': name, 'active': active});
  }

  Future<void> deleteCategory(int id) async {
    await _request('DELETE', '/api/admin/menu/categories/$id');
  }

  Future<void> setCatalogItemActive(int tenantId, int id, bool active) async {
    final path = '/api/admin/menu/items/$id';
    final multipart = http.MultipartRequest('PUT', origin.resolve(path));
    multipart.fields.addAll({'tenant_id': '$tenantId', 'active': '$active'});
    await _request('PUT', path, multipart: multipart);
  }

  Future<void> saveCatalogItem(
    int tenantId, {
    int? id,
    required String name,
    required int priceCents,
    required String description,
    required int? categoryId,
    required ({Uint8List bytes, String filename})? photo,
  }) async {
    final method = id == null ? 'POST' : 'PUT';
    final path = id == null ? '/api/admin/menu/items' : '/api/admin/menu/items/$id';
    final multipart = http.MultipartRequest(method, origin.resolve(path));
    multipart.fields.addAll({
      'tenant_id': '$tenantId',
      'name': name,
      'price_cents': '$priceCents',
      if (description.isNotEmpty) 'description': description,
      if (description.isEmpty && id != null) 'clear_description': 'true',
      if (categoryId != null || id != null) 'category_id': '${categoryId ?? -1}',
    });
    if (photo != null) {
      multipart.files.add(http.MultipartFile.fromBytes('image', photo.bytes, filename: photo.filename));
    }
    await _request(method, path, multipart: multipart);
  }

  Future<void> updateOrderPush(Map<String, String> registration,
      {required bool enabled}) async {
    await _request(enabled ? 'PUT' : 'DELETE', '/api/admin/management-push/device',
        body: registration);
  }

  void clearSession() => _session = null;

  Future<void> logout() async {
    try {
      await _request('POST', '/api/admin/auth/logout');
    } finally {
      clearSession();
    }
  }

  void close() => _client.close(force: true);

  Future<dynamic> _request(
    String method, String path, {
    Map<String, Object?>? body,
    http.MultipartRequest? multipart,
    bool authenticated = true,
  }) async {
    final request = await _client.openUrl(method, origin.resolve(path));
    request.followRedirects = false;
    request.headers.set(HttpHeaders.acceptHeader, 'application/json');
    final session = _session;
    if (authenticated && session != null) request.cookies.add(session);
    if (multipart != null) {
      final stream = multipart.finalize();
      multipart.headers.forEach((name, value) => request.headers.set(name, value));
      request.contentLength = multipart.contentLength;
      await request.addStream(stream).timeout(const Duration(seconds: 30));
    } else if (body != null) {
      request.headers.contentType = ContentType.json;
      request.write(jsonEncode(body));
    }
    final response = await request.close().timeout(const Duration(seconds: 20));
    final content = await utf8.decoder.bind(response).join().timeout(const Duration(seconds: 20));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      if (authenticated && response.statusCode == 401) clearSession();
      throw ManagementApiError(response.statusCode);
    }
    if (path == '/api/admin/auth/login') {
      for (final cookie in response.cookies) {
        if (cookie.name == 'admin_session' && cookie.secure && cookie.httpOnly && cookie.value.isNotEmpty) {
          _session = cookie;
        }
      }
      if (_session == null) throw const ManagementApiError(401);
    }
    return content.isEmpty ? null : jsonDecode(content);
  }
}

class ManagementApiError implements Exception {
  const ManagementApiError(this.status);

  final int status;
}
