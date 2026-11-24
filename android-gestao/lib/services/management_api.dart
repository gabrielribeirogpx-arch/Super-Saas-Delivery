import 'dart:convert';
import 'dart:io';

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

  Future<int> login(String store, String email, String password) async {
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
      return profile['tenant_id'] as int;
    } catch (_) {
      _session = null;
      rethrow;
    }
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

  void clearSession() => _session = null;

  Future<void> logout() async {
    try {
      await _request('POST', '/api/admin/auth/logout');
    } finally {
      clearSession();
    }
  }

  void close() => _client.close(force: true);

  Future<dynamic> _request(String method, String path, {Map<String, String>? body}) async {
    final request = await _client.openUrl(method, origin.resolve(path));
    request.followRedirects = false;
    request.headers.set(HttpHeaders.acceptHeader, 'application/json');
    final session = _session;
    if (session != null) request.cookies.add(session);
    if (body != null) {
      request.headers.contentType = ContentType.json;
      request.write(jsonEncode(body));
    }
    final response = await request.close().timeout(const Duration(seconds: 20));
    final content = await utf8.decoder.bind(response).join().timeout(const Duration(seconds: 20));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      if (response.statusCode == 401) clearSession();
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
