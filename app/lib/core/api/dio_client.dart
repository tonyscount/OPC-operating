import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiClient {
  /// 生产环境可通过环境变量或构建参数覆盖
  static String baseUrl = 'http://localhost:8000/api/v1';

  final Dio _dio;
  final _storage = const FlutterSecureStorage();

  /// 全局 429 回调
  static void Function(int retryAfterSec, String message)? onRateLimited;
  /// 全局 401 回调 (token 刷新失败 → 跳转登录)
  static void Function()? onSessionExpired;

  ApiClient._()
      : _dio = Dio(BaseOptions(
          baseUrl: baseUrl,
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 30),
          headers: {'Content-Type': 'application/json'},
        )) {
    _dio.interceptors.add(_AuthInterceptor(_storage));
    _dio.interceptors.add(_TokenRefreshInterceptor(_storage, _dio));
    _dio.interceptors.add(_RateLimitInterceptor());
  }

  static final ApiClient instance = ApiClient._();

  // ---- HTTP methods ----
  Future<Response> post(String path, {dynamic data}) =>
      _dio.post(path, data: data);
  Future<Response> get(String path, {Map<String, dynamic>? params}) =>
      _dio.get(path, queryParameters: params);
  Future<Response> patch(String path, {dynamic data}) =>
      _dio.patch(path, data: data);
  Future<Response> delete(String path) => _dio.delete(path);

  // ---- Token storage ----
  Future<void> setTokens(String access, {String? refresh}) async {
    await _storage.write(key: 'jwt_token', value: access);
    if (refresh != null) {
      await _storage.write(key: 'refresh_token', value: refresh);
    }
  }

  Future<String?> get accessToken => _storage.read(key: 'jwt_token');
  Future<String?> get refreshToken => _storage.read(key: 'refresh_token');
  Future<void> clearTokens() async {
    try { await post('/auth/logout'); } catch (_) {}
    await _storage.delete(key: 'jwt_token');
    await _storage.delete(key: 'refresh_token');
  }
}

// ====== Interceptors ======

class _AuthInterceptor extends Interceptor {
  final FlutterSecureStorage _storage;
  _AuthInterceptor(this._storage);

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    final token = await _storage.read(key: 'jwt_token');
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }
}

/// Token 刷新拦截器 — 401 时尝试用 refresh_token 换新 token，失败则跳登录
class _TokenRefreshInterceptor extends Interceptor {
  final FlutterSecureStorage _storage;
  final Dio _dio;
  bool _isRefreshing = false;

  _TokenRefreshInterceptor(this._storage, this._dio);

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode != 401) {
      handler.next(err);
      return;
    }
    // 排除 login / refresh 本身的 401
    if (err.requestOptions.path.contains('/auth/login') ||
        err.requestOptions.path.contains('/auth/refresh')) {
      handler.next(err);
      return;
    }

    if (_isRefreshing) {
      // 等刷新完成再重试
      await Future.delayed(const Duration(milliseconds: 500));
      try {
        final resp = await _retry(err.requestOptions);
        handler.resolve(resp);
      } catch (_) {
        _logout();
        handler.next(err);
      }
      return;
    }

    _isRefreshing = true;
    try {
      final rt = await _storage.read(key: 'refresh_token');
      if (rt == null) throw Exception('No refresh token');

      final refreshResp = await Dio(BaseOptions(
        baseUrl: _dio.options.baseUrl,
        connectTimeout: const Duration(seconds: 10),
      )).post('/auth/refresh', data: {'refresh_token': rt});

      final newAccess = refreshResp.data['access_token'];
      final newRefresh = refreshResp.data['refresh_token'];
      await _storage.write(key: 'jwt_token', value: newAccess);
      if (newRefresh != null) {
        await _storage.write(key: 'refresh_token', value: newRefresh);
      }

      _isRefreshing = false;
      final resp = await _retry(err.requestOptions);
      handler.resolve(resp);
    } catch (_) {
      _isRefreshing = false;
      _logout();
      handler.next(err);
    }
  }

  Future<Response<dynamic>> _retry(RequestOptions options) async {
    final token = await _storage.read(key: 'jwt_token');
    final opts = options.copyWith(
      headers: {
        ...options.headers,
        'Authorization': 'Bearer $token',
      },
    );
    return _dio.fetch(opts);
  }

  void _logout() {
    _storage.delete(key: 'jwt_token');
    _storage.delete(key: 'refresh_token');
    if (ApiClient.onSessionExpired != null) {
      ApiClient.onSessionExpired!();
    }
  }
}

/// 429 限流拦截器
class _RateLimitInterceptor extends Interceptor {
  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    if (err.response?.statusCode == 429) {
      final retryAfter = int.tryParse(
        err.response?.headers.value('Retry-After') ?? '60',
      ) ?? 60;
      final message = err.response?.data is Map
          ? (err.response?.data['detail'] ?? '请求过于频繁，请稍后再试')
          : '请求过于频繁，请稍后再试';

      if (ApiClient.onRateLimited != null) {
        ApiClient.onRateLimited!(retryAfter, message.toString());
      } else {
        debugPrint('[RateLimit] 429 — retry after ${retryAfter}s: $message');
      }
    }
    handler.next(err);
  }
}
