import 'package:flutter/material.dart';
import '../../core/api/dio_client.dart';

class DiscoverPage extends StatefulWidget {
  const DiscoverPage({super.key});
  @override
  State<DiscoverPage> createState() => _DiscoverPageState();
}

class _DiscoverPageState extends State<DiscoverPage> {
  List _items = [];
  List _circles = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final nearby = await ApiClient.instance.get('/discover/nearby', params: {'lat': 31.23, 'lng': 121.47, 'radius_km': 20});
      final circles = await ApiClient.instance.get('/discover/circles');
      setState(() { _items = nearby.data['items'] ?? []; _circles = circles.data['circles'] ?? []; _loading = false; });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  Future<void> _greet(String userId) async {
    try {
      await ApiClient.instance.post('/discover/greet', data: {'to_user_id': userId, 'source': 'lbs'});
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('已打招呼')));
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : Column(
                children: [
                  // 圈子
                  SizedBox(
                    height: 60,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      itemCount: _circles.length,
                      separatorBuilder: (_, __) => const SizedBox(width: 8),
                      itemBuilder: (_, i) {
                        final c = _circles[i];
                        return Chip(
                          avatar: Icon(_circleIcon(c['category']), size: 16),
                          label: Text('${c['name']} ${c['member_count']}'),
                          backgroundColor: Colors.white.withOpacity(0.08),
                        );
                      },
                    ),
                  ),
                  // 附近列表
                  Expanded(
                    child: ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      itemCount: _items.length,
                      itemBuilder: (_, i) {
                        final item = _items[i];
                        final isPeer = item['type'] == 'peer';
                        return Card(
                          margin: const EdgeInsets.only(bottom: 8),
                          child: ListTile(
                            leading: CircleAvatar(
                              radius: 22,
                              backgroundColor: isPeer ? const Color(0xFF00D4FF) : Colors.green,
                              child: Icon(isPeer ? Icons.person : Icons.router, color: Colors.black),
                            ),
                            title: Text(item['display_name'] ?? item['name'] ?? ''),
                            subtitle: Row(
                              children: [
                                Text('${item['distance_km']}km', style: Theme.of(context).textTheme.bodyMedium),
                                if (isPeer) ...[
                                  const SizedBox(width: 8),
                                  if (item['skills'] != null)
                                    for (var s in (item['skills'] as List).take(2))
                                      Padding(
                                        padding: const EdgeInsets.only(right: 4),
                                        child: Text('#$s', style: const TextStyle(color: Color(0xFF00D4FF), fontSize: 11)),
                                      ),
                                ] else ...[
                                  const SizedBox(width: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: item['status'] == 'online' ? Colors.green.withOpacity(0.15) : Colors.grey.withOpacity(0.15),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(item['status'] ?? '', style: TextStyle(fontSize: 10, color: item['status'] == 'online' ? Colors.green : Colors.grey)),
                                  ),
                                ],
                              ],
                            ),
                            trailing: FilledButton(
                              onPressed: () => _greet(item['id']),
                              style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 16)),
                              child: const Text('打招呼'),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
      ),
    );
  }

  IconData _circleIcon(String? cat) {
    switch (cat) {
      case 'certification': return Icons.verified;
      case 'hardware': return Icons.memory;
      case 'software': return Icons.cloud;
      case 'protocol': return Icons.code;
      default: return Icons.group;
    }
  }
}
