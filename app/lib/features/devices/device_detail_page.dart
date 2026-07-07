import 'package:flutter/material.dart';
import '../../core/api/dio_client.dart';

class DeviceDetailPage extends StatefulWidget {
  final String deviceId;
  const DeviceDetailPage({super.key, required this.deviceId});

  @override
  State<DeviceDetailPage> createState() => _DeviceDetailPageState();
}

class _DeviceDetailPageState extends State<DeviceDetailPage> {
  Map? _data;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final resp = widget.deviceId == 'me'
          ? await ApiClient.instance.get('/users/${widget.deviceId}/business-card')
          : await ApiClient.instance.get('/devices/${widget.deviceId}');
      setState(() { _data = resp.data; _loading = false; });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    if (_data == null) return const Scaffold(body: Center(child: Text('加载失败')));

    // 名片模式
    if (_data!.containsKey('user')) return _buildBusinessCard(context);
    return _buildDeviceDetail(context);
  }

  Widget _buildBusinessCard(BuildContext context) {
    final user = _data!['user'];
    final skills = _data!['skills'] as List? ?? [];
    final devices = _data!['devices'] as List? ?? [];
    final status = _data!['status'];
    final stats = _data!['stats'];

    return Scaffold(
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            SliverAppBar(
              expandedHeight: 240,
              pinned: true,
              flexibleSpace: FlexibleSpaceBar(
                background: Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [const Color(0xFF00D4FF).withOpacity(0.3), Colors.transparent],
                    ),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const CircleAvatar(radius: 48, backgroundColor: Color(0xFF00D4FF), child: Icon(Icons.person, size: 48, color: Colors.black)),
                      const SizedBox(height: 8),
                      Text(user['display_name'] ?? user['username'] ?? '', style: Theme.of(context).textTheme.titleLarge),
                      if (status != null) Text('${status['emoji'] ?? ''} ${status['text'] ?? ''}', style: Theme.of(context).textTheme.bodyMedium),
                    ],
                  ),
                ),
              ),
              actions: [IconButton(icon: const Icon(Icons.bookmark_border), onPressed: () {})],
            ),
            // 技能标签
            if (skills.isNotEmpty)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Wrap(
                    spacing: 8, runSpacing: 8,
                    children: skills.map((s) => Chip(
                      label: Text('${s['name']} · ${s['level']}'),
                      backgroundColor: const Color(0xFF00D4FF).withOpacity(0.1),
                      side: BorderSide.none,
                    )).toList(),
                  ),
                ),
              ),
            // 统计
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    _statCol('设备', '${stats['devices']}'),
                    _statCol('粉丝', '${stats['followers']}'),
                    _statCol('关注', '${stats['following']}'),
                  ],
                ),
              ),
            ),
            // 设备列表
            if (devices.isNotEmpty)
              SliverList(
                delegate: SliverChildBuilderDelegate(
                  (_, i) => Card(
                    margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                    child: ListTile(
                      leading: const Icon(Icons.router, color: Color(0xFF00D4FF)),
                      title: Text(devices[i]['name'] ?? ''),
                      subtitle: Text(devices[i]['ip_address'] ?? ''),
                      trailing: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: devices[i]['status'] == 'online' ? Colors.green.withOpacity(0.15) : Colors.grey.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(devices[i]['status'] ?? '', style: TextStyle(fontSize: 11, color: devices[i]['status'] == 'online' ? Colors.green : Colors.grey)),
                      ),
                    ),
                  ),
                  childCount: devices.length,
                ),
              ),
          ],
        ),
      ),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () {},
                icon: const Icon(Icons.chat_bubble_outline),
                label: const Text('发消息'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FilledButton.icon(
                onPressed: () {},
                icon: const Icon(Icons.engineering),
                label: const Text('立即协助'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDeviceDetail(BuildContext context) {
    final d = _data!;
    return Scaffold(
      appBar: AppBar(title: Text(d['name'] ?? '设备详情'), actions: [IconButton(icon: const Icon(Icons.bookmark_border), onPressed: () {})]),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (d['image_url'] != null) ClipRRect(borderRadius: BorderRadius.circular(16), child: Image.network(d['image_url'], height: 200, width: double.infinity, fit: BoxFit.cover)),
            const SizedBox(height: 16),
            Text(d['name'] ?? '', style: Theme.of(context).textTheme.headlineLarge),
            const SizedBox(height: 8),
            Row(children: [
              Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4), decoration: BoxDecoration(color: d['status'] == 'online' ? Colors.green.withOpacity(0.15) : Colors.grey.withOpacity(0.15), borderRadius: BorderRadius.circular(12)), child: Text(d['status'] ?? '', style: TextStyle(color: d['status'] == 'online' ? Colors.green : Colors.grey, fontSize: 12))),
              const SizedBox(width: 12),
              Text(d['ip_address'] ?? 'IP 未配置', style: Theme.of(context).textTheme.bodyMedium),
            ]),
            const SizedBox(height: 16),
            if (d['tags'] != null) Wrap(spacing: 8, children: (d['tags'] as List).map((t) => Chip(label: Text('$t'), backgroundColor: Colors.white.withOpacity(0.08), side: BorderSide.none)).toList()),
            const SizedBox(height: 16),
            if (d['specs'] != null) ...(d['specs'] as Map).entries.map((e) => Padding(padding: const EdgeInsets.only(bottom: 8), child: Text('${e.key}: ${e.value}', style: Theme.of(context).textTheme.bodyMedium))),
          ],
        ),
      ),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.all(16),
        child: FilledButton.icon(
          onPressed: () {},
          icon: const Icon(Icons.settings_remote),
          label: const Text('远程协助'),
          style: FilledButton.styleFrom(minimumSize: const Size(double.infinity, 52)),
        ),
      ),
    );
  }

  Widget _statCol(String label, String value) {
    return Column(children: [Text(value, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Color(0xFF00D4FF))), Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey))]);
  }
}
