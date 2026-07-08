import 'package:flutter/material.dart';
import '../../core/api/dio_client.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  List _posts = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final resp = await ApiClient.instance
          .get('/social/posts', params: {'feed_type': 'all', 'page_size': '50'});
      setState(() {
        _posts = resp.data['items'] ?? [];
        _loading = false;
      });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  Future<void> _likePost(String id) async {
    try {
      await ApiClient.instance.post('/social/posts/$id/like');
      _load();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B1120),
      body: SafeArea(
        child: Column(
          children: [
            // Header
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: Row(
                children: [
                  const CircleAvatar(
                      radius: 18,
                      backgroundColor: Color(0xFF00D4FF),
                      child: Icon(Icons.person, color: Colors.black, size: 20)),
                  const SizedBox(width: 10),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('OPC Feed',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w700)),
                      Text('一人公司社交圈',
                          style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ),
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.edit_outlined, color: Color(0xFF00D4FF)),
                    onPressed: () => _showCompose(),
                  ),
                ],
              ),
            ),
            const Divider(height: 1, color: Color(0xFF1E293B)),
            // Feed
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : RefreshIndicator(
                      onRefresh: _load,
                      child: _posts.isEmpty
                          ? ListView(children: const [
                              SizedBox(height: 80),
                              Center(
                                  child: Text('暂无动态，发布第一条吧',
                                      style: TextStyle(color: Colors.grey))),
                            ])
                          : ListView.builder(
                              itemCount: _posts.length,
                              padding: const EdgeInsets.only(bottom: 80),
                              itemBuilder: (_, i) => _PostCard(
                                    _posts[i],
                                    onLike: () => _likePost(_posts[i]['id']),
                                  ),
                            ),
                    ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFF00D4FF),
        child: const Icon(Icons.add, color: Colors.black),
        onPressed: () => _showCompose(),
      ),
    );
  }

  void _showCompose() {
    final ctrl = TextEditingController();
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF1E293B),
      builder: (_) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: ctrl,
              maxLines: 3,
              decoration: const InputDecoration(
                hintText: '分享你的经验和想法...',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: () async {
                  if (ctrl.text.trim().isEmpty) return;
                  try {
                    await ApiClient.instance
                        .post('/social/posts', data: {'content': ctrl.text.trim(), 'visibility': 'public'});
                    if (mounted) {
                      Navigator.pop(context);
                      _load();
                    }
                  } catch (e) {
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('发布失败: $e')));
                    }
                  }
                },
                child: const Text('发布'),
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}

class _PostCard extends StatelessWidget {
  final Map item;
  final VoidCallback onLike;
  const _PostCard(this.item, {required this.onLike});

  String _timeAgo(String iso) {
    try {
      final diff = DateTime.now().difference(DateTime.parse(iso));
      if (diff.inMinutes < 60) return '${diff.inMinutes}分钟前';
      if (diff.inHours < 24) return '${diff.inHours}小时前';
      return '${diff.inDays}天前';
    } catch (_) {
      return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    final liked = item['is_liked'] == true;
    return Card(
      color: const Color(0xFF111827),
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const CircleAvatar(
                    radius: 14,
                    backgroundColor: Color(0xFF1E293B),
                    child: Icon(Icons.person, size: 16, color: Color(0xFF00D4FF))),
                const SizedBox(width: 8),
                Text('Engineer_OPC',
                    style: Theme.of(context)
                        .textTheme
                        .bodyMedium
                        ?.copyWith(fontWeight: FontWeight.w600)),
                const Spacer(),
                Text(_timeAgo(item['created_at'] ?? ''),
                    style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
            const SizedBox(height: 10),
            Text(item['content'] ?? '',
                style: Theme.of(context).textTheme.bodyLarge,
                maxLines: 6,
                overflow: TextOverflow.ellipsis),
            const SizedBox(height: 10),
            Row(
              children: [
                GestureDetector(
                  onTap: onLike,
                  child: Row(
                    children: [
                      Icon(liked ? Icons.favorite : Icons.favorite_border,
                          size: 18,
                          color: liked ? Colors.redAccent : Colors.grey),
                      const SizedBox(width: 4),
                      Text('${item['like_count'] ?? 0}',
                          style: const TextStyle(color: Colors.grey, fontSize: 12)),
                    ],
                  ),
                ),
                const SizedBox(width: 24),
                const Icon(Icons.chat_bubble_outline, size: 18, color: Colors.grey),
                const SizedBox(width: 4),
                Text('${item['comment_count'] ?? 0}',
                    style: const TextStyle(color: Colors.grey, fontSize: 12)),
                const Spacer(),
                Text('👁 ${item['view_count'] ?? 0}',
                    style: const TextStyle(color: Colors.grey, fontSize: 11)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
