import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/api/dio_client.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _tenantCtrl = TextEditingController(text: 'demo');
  final _userCtrl = TextEditingController(text: 'admin');
  final _passCtrl = TextEditingController(text: 'admin123456');
  bool _loading = false;

  Future<void> _login() async {
    setState(() => _loading = true);
    try {
      final resp = await ApiClient.instance.post('/auth/login', data: {
        'tenant_slug': _tenantCtrl.text.trim(),
        'username': _userCtrl.text.trim(),
        'password': _passCtrl.text,
      });
      await ApiClient.instance.setToken(resp.data['access_token']);
      if (mounted) context.go('/home');
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('登录失败: $e'), backgroundColor: Colors.red),
      );
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.memory, size: 72, color: Color(0xFF00D4FF)),
              const SizedBox(height: 16),
              Text('OPC Platform', style: Theme.of(context).textTheme.headlineLarge),
              const SizedBox(height: 4),
              Text('一人公司工业社交平台', style: Theme.of(context).textTheme.bodyMedium),
              const SizedBox(height: 48),
              TextField(
                controller: _tenantCtrl,
                decoration: const InputDecoration(labelText: '租户标识', prefixIcon: Icon(Icons.business)),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _userCtrl,
                decoration: const InputDecoration(labelText: '用户名', prefixIcon: Icon(Icons.person)),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _passCtrl,
                obscureText: true,
                decoration: const InputDecoration(labelText: '密码', prefixIcon: Icon(Icons.lock)),
                onSubmitted: (_) => _login(),
              ),
              const SizedBox(height: 32),
              SizedBox(
                width: double.infinity,
                height: 48,
                child: FilledButton(
                  onPressed: _loading ? null : _login,
                  child: _loading ? const CircularProgressIndicator() : const Text('登录'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
