import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../features/auth/login_page.dart';
import '../../features/home/home_page.dart';
import '../../features/discover/discover_page.dart';
import '../../features/devices/device_detail_page.dart';

class AppRouter {
  static final router = GoRouter(
    initialLocation: '/login',
    routes: [
      GoRoute(path: '/login', builder: (_, __) => const LoginPage()),
      ShellRoute(
        builder: (_, __, child) => MainShell(child: child),
        routes: [
          GoRoute(path: '/home', builder: (_, __) => const HomePage()),
          GoRoute(path: '/discover', builder: (_, __) => const DiscoverPage()),
          GoRoute(path: '/devices/:id', builder: (_, state) =>
              DeviceDetailPage(deviceId: state.pathParameters['id']!)),
          GoRoute(path: '/profile', builder: (_, __) => const Scaffold(body: Center(child: Text('我的')))),
        ],
      ),
    ],
  );
}

class MainShell extends StatelessWidget {
  final Widget child;
  const MainShell({super.key, required this.child});

  int _currentIndex(String location) {
    if (location.startsWith('/home')) return 0;
    if (location.startsWith('/discover')) return 1;
    if (location.startsWith('/devices')) return 2;
    return 3;
  }

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.toString();
    return Scaffold(
      body: child,
      extendBody: true,
      bottomNavigationBar: ClipRRect(
        child: Container(
          margin: const EdgeInsets.fromLTRB(20, 0, 20, 12),
          decoration: BoxDecoration(
            color: Colors.black.withOpacity(0.65),
            borderRadius: BorderRadius.circular(24),
            boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.3), blurRadius: 20)],
          ),
          child: BottomNavigationBar(
            currentIndex: _currentIndex(location),
            onTap: (i) {
              final routes = ['/home', '/discover', '/devices/me', '/profile'];
              GoRouter.of(context).go(routes[i]);
            },
            items: const [
              BottomNavigationBarItem(icon: Icon(Icons.chat_bubble_outline), label: '消息'),
              BottomNavigationBarItem(icon: Icon(Icons.widgets_outlined), label: '设备'),
              BottomNavigationBarItem(icon: Icon(Icons.travel_explore_outlined), label: '发现'),
              BottomNavigationBarItem(icon: Icon(Icons.person_outline), label: '我的'),
            ],
          ),
        ),
      ),
    );
  }
}
