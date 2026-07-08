import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../features/auth/login_page.dart';
import '../../features/home/home_page.dart';
import '../../features/discover/discover_page.dart';
import '../../features/knowledge/knowledge_page.dart';
import '../../features/agent/agent_page.dart';
import '../../core/api/dio_client.dart';

class AppRouter {
  static final router = GoRouter(
    initialLocation: '/login',
    routes: [
      GoRoute(path: '/login', builder: (_, __) => const LoginPage()),
      ShellRoute(
        builder: (_, __, child) => MainShell(child: child),
        routes: [
          GoRoute(
              path: '/home', builder: (_, __) => const HomePage()),
          GoRoute(
              path: '/knowledge',
              builder: (_, __) => const KnowledgePage()),
          GoRoute(
              path: '/agent', builder: (_, __) => const AgentPage()),
          GoRoute(
              path: '/discover',
              builder: (_, __) => const DiscoverPage()),
          GoRoute(
            path: '/profile',
            builder: (ctx, _) => Scaffold(
              backgroundColor: const Color(0xFF0B1120),
              body: SafeArea(
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const CircleAvatar(
                          radius: 40,
                          backgroundColor: Color(0xFF00D4FF),
                          child: Icon(Icons.person,
                              size: 40, color: Colors.black)),
                      const SizedBox(height: 12),
                      const Text('我的',
                          style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                              color: Colors.white)),
                      const SizedBox(height: 24),
                      FilledButton(
                        onPressed: () async {
                          await ApiClient.instance.clearTokens();
                          if (ctx.mounted) ctx.go('/login');
                        },
                        child: const Text('退出登录'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
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
    if (location.startsWith('/knowledge')) return 1;
    if (location.startsWith('/agent')) return 2;
    if (location.startsWith('/discover')) return 3;
    return 4;
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
            boxShadow: [
              BoxShadow(
                  color: Colors.black.withOpacity(0.3), blurRadius: 20)
            ],
          ),
          child: BottomNavigationBar(
            currentIndex: _currentIndex(location),
            onTap: (i) {
              final routes = [
                '/home',
                '/knowledge',
                '/agent',
                '/discover',
                '/profile'
              ];
              GoRouter.of(context).go(routes[i]);
            },
            backgroundColor: Colors.transparent,
            selectedItemColor: const Color(0xFF00D4FF),
            unselectedItemColor: Colors.grey,
            type: BottomNavigationBarType.fixed,
            items: const [
              BottomNavigationBarItem(
                  icon: Icon(Icons.chat_bubble_outline), label: '社群'),
              BottomNavigationBarItem(
                  icon: Icon(Icons.menu_book_outlined), label: '知识库'),
              BottomNavigationBarItem(
                  icon: Icon(Icons.psychology_outlined), label: 'Agent'),
              BottomNavigationBarItem(
                  icon: Icon(Icons.travel_explore_outlined), label: '发现'),
              BottomNavigationBarItem(
                  icon: Icon(Icons.person_outline), label: '我的'),
            ],
          ),
        ),
      ),
    );
  }
}
