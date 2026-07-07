import 'package:flutter/material.dart';
import '../../core/api/dio_client.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  List _items = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadFeed();
  }

  Future<void> _loadFeed() async {
    try {
      final resp = await ApiClient.instance.get('/discover/feed');
      setState(() { _items = resp.data['items'] ?? []; _loading = false; });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            // 顶部状态栏
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
                child: Row(
                  children: [
                    const CircleAvatar(radius: 20, backgroundColor: Color(0xFF00D4FF), child: Icon(Icons.person, color: Colors.black)),
                    const SizedBox(width: 12),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Engineer_OPC', style: Theme.of(context).textTheme.titleLarge),
                        Text('🟢 在线 · 运维中', style: Theme.of(context).textTheme.bodyMedium),
                      ],
                    ),
                    const Spacer(),
                    _statusBubble('🔧', '运维中'),
                  ],
                ),
              ),
            ),
            // 混合信息流
            if (_loading)
              const SliverFillRemaining(child: Center(child: CircularProgressIndicator()))
            else
              SliverList(
                delegate: SliverChildBuilderDelegate(
                  (ctx, i) => _items[i]['type'] == 'post' ? _PostCard(_items[i]) : _DeviceCard(_items[i]),
                  childCount: _items.length,
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _statusBubble(String emoji, String text) {
    return GestureDetector(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.08),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text('$emoji $text', style: const TextStyle(fontSize: 12)),
      ),
    );
  }
}

// ====== 动态卡片 ======
class _PostCard extends StatelessWidget {
  final Map item;
  const _PostCard(this.item);

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              const CircleAvatar(radius: 16, child: Icon(Icons.person, size: 18)),
              const SizedBox(width: 8),
              Text('Engineer_OPC', style: Theme.of(context).textTheme.bodyLarge),
              const Spacer(),
              Text(_timeAgo(item['created_at'] ?? ''), style: Theme.of(context).textTheme.bodyMedium),
            ]),
            const SizedBox(height: 12),
            Text(item['content'] ?? '', style: Theme.of(context).textTheme.bodyLarge, maxLines: 5, overflow: TextOverflow.ellipsis),
            const SizedBox(height: 12),
            Row(children: [
              _actionBtn(Icons.favorite_border, '${item['like_count'] ?? 0}'),
              const SizedBox(width: 24),
              _actionBtn(Icons.chat_bubble_outline, '${item['comment_count'] ?? 0}'),
            ]),
          ],
        ),
      ),
    );
  }

  Widget _actionBtn(IconData icon, String label) {
    return Row(children: [Icon(icon, size: 18, color: Colors.grey), const SizedBox(width: 4), Text(label, style: const TextStyle(color: Colors.grey, fontSize: 12))]);
  }

  String _timeAgo(String iso) {
    try {
      final diff = DateTime.now().difference(DateTime.parse(iso));
      if (diff.inMinutes < 60) return '${diff.inMinutes}分钟前';
      if (diff.inHours < 24) return '${diff.inHours}小时前';
      return '${diff.inDays}天前';
    } catch (_) { return ''; }
  }
}

// ====== 设备卡片 ======
class _DeviceCard extends StatelessWidget {
  final Map item;
  const _DeviceCard(this.item);

  @override
  Widget build(BuildContext context) {
    final online = item['status'] == 'online';
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 60, height: 60,
              decoration: BoxDecoration(
                color: online ? const Color(0xFF00D4FF).withOpacity(0.1) : Colors.grey.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(Icons.router, size: 32, color: online ? const Color(0xFF00D4FF) : Colors.grey),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(item['name'] ?? '', style: Theme.of(context).textTheme.bodyLarge),
                  const SizedBox(height: 4),
                  Text(item['ip_address'] ?? 'IP 未配置', style: Theme.of(context).textTheme.bodyMedium),
                  if (item['location'] != null) Text(item['location'], style: Theme.of(context).textTheme.bodyMedium),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: online ? Colors.green.withOpacity(0.15) : Colors.grey.withOpacity(0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(online ? '在线' : '离线', style: TextStyle(color: online ? Colors.green : Colors.grey, fontSize: 12)),
            ),
          ],
        ),
      ),
    );
  }
}
