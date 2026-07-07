import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiClient {
  static const _baseUrl = 'http://localhost:8000/api/v1';
  final Dio _dio;
  final _storage = const FlutterSecureStorage();

  /// 全局 429 回调 — App 启动时可覆盖以使用 SnackBar/Toast
  static void Function(int retryAfterSec, String message)? onRateLimited;

  ApiClient._()
      : _dio = Dio(BaseOptions(
          baseUrl: _baseUrl,
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 30),
          headers: {'Content-Type': 'application/json'},
        )) {
    _dio.interceptors.add(_AuthInterceptor(_storage));
    _dio.interceptors.add(_RateLimitInterceptor());
  }

  static final ApiClient instance = ApiClient._();

  Future<Response> post(String path, {dynamic data}) => _dio.post(path, data: data);
  Future<Response> get(String path, {Map<String, dynamic>? params}) =>
      _dio.get(path, queryParameters: params);
  Future<Response> patch(String path, {dynamic data}) => _dio.patch(path, data: data);
  Future<Response> delete(String path) => _dio.delete(path);

  Future<void> setToken(String token) => _storage.write(key: 'jwt_token', value: token);
  Future<String?> get token => _storage.read(key: 'jwt_token');
  Future<void> clearToken() => _storage.delete(key: 'jwt_token');
}

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

/// 429 限流拦截器 — 拦截限流响应，触发全局或默认回调
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
        // 默认: 打印日志，不崩溃
        debugPrint('[RateLimit] 429 hit — retry after ${retryAfter}s: $message');
      }
    }
    handler.next(err);
  }
}
