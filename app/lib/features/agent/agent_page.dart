import 'package:flutter/material.dart';
import '../../core/api/dio_client.dart';

class AgentPage extends StatefulWidget {
  const AgentPage({super.key});
  @override
  State<AgentPage> createState() => _AgentPageState();
}

class _AgentPageState extends State<AgentPage> {
  final _msgCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  List<Map<String, String>> _messages = [];
  List<Map<String, String>> _agents = [];
  String? _selectedAgent;
  bool _loading = false;
  bool _agentsLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchAgents();
  }

  Future<void> _fetchAgents() async {
    try {
      final resp = await ApiClient.instance.get('/agent/list');
      final list = (resp.data?['agents'] as List?) ?? [];
      setState(() {
        _agents = list.map<Map<String, String>>((a) {
          return {
            'name': a['name']?.toString() ?? '',
            'emoji': a['emoji']?.toString() ?? '🤖',
            'desc': a['description']?.toString() ?? '',
          };
        }).toList();
        _agentsLoading = false;
        if (_agents.isNotEmpty && _selectedAgent == null) {
          _selectedAgent = _agents.first['name'];
        }
      });
    } catch (_) {
      setState(() => _agentsLoading = false);
    }
  }

  Future<void> _send() async {
    final text = _msgCtrl.text.trim();
    if (text.isEmpty || _selectedAgent == null) return;

    setState(() {
      _messages.add({'role': 'user', 'content': text});
      _msgCtrl.clear();
      _loading = true;
    });
    _scrollToBottom();

    try {
      final resp = await ApiClient.instance.post('/agent/run', data: {
        'agent_name': _selectedAgent,
        'message': text,
        'mode': 'single',
      });
      final output = resp.data['output'] ?? resp.data['error'] ?? '无响应';
      setState(() {
        _messages.add({'role': 'assistant', 'content': output.toString()});
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _messages.add({'role': 'assistant', 'content': '请求失败: $e'});
        _loading = false;
      });
    }
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(_scrollCtrl.position.maxScrollExtent,
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeOut);
      }
    });
  }

  @override
  void dispose() {
    _msgCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final current = _agents.isNotEmpty && _selectedAgent != null
        ? _agents.firstWhere((a) => a['name'] == _selectedAgent,
            orElse: () => _agents.first)
        : null;

    return Scaffold(
      backgroundColor: const Color(0xFF0B1120),
      body: SafeArea(
        child: Column(
          children: [
            // Header + agent selector (horizontally scrollable)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Text('AI Agent',
                          style: TextStyle(
                              fontSize: 16, fontWeight: FontWeight.w700)),
                      const SizedBox(width: 8),
                      Text('${_agents.length} 个可用',
                          style: const TextStyle(
                              fontSize: 11, color: Colors.white38)),
                    ],
                  ),
                  const SizedBox(height: 8),
                  SizedBox(
                    height: 34,
                    child: _agentsLoading
                        ? const Text('加载中...',
                            style:
                                TextStyle(fontSize: 12, color: Colors.white24))
                        : ListView.separated(
                            scrollDirection: Axis.horizontal,
                            itemCount: _agents.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(width: 4),
                            itemBuilder: (_, i) {
                              final a = _agents[i];
                              final selected = _selectedAgent == a['name'];
                              return ChoiceChip(
                                label: Text(
                                  '${a['emoji']} ${a['name']}',
                                  style: TextStyle(
                                      fontSize: 11,
                                      color: selected
                                          ? Colors.black
                                          : Colors.white70),
                                ),
                                selected: selected,
                                selectedColor: const Color(0xFF00D4FF),
                                backgroundColor: const Color(0xFF1E293B),
                                side: BorderSide.none,
                                onSelected: (_) =>
                                    setState(() => _selectedAgent = a['name']),
                              );
                            },
                          ),
                  ),
                ],
              ),
            ),
            // Current agent description
            if (current != null && (current['desc']?.isNotEmpty ?? false))
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
                child: Text(current['desc']!,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style:
                        const TextStyle(fontSize: 11, color: Colors.white38)),
              ),
            const Divider(height: 1, color: Color(0xFF1E293B)),
            // Chat
            Expanded(
              child: ListView.builder(
                controller: _scrollCtrl,
                padding: const EdgeInsets.all(12),
                itemCount: _messages.length + (_loading ? 1 : 0),
                itemBuilder: (_, i) {
                  if (_loading && i == _messages.length) {
                    return const Padding(
                      padding: EdgeInsets.all(12),
                      child: Row(
                        children: [
                          SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2)),
                          SizedBox(width: 8),
                          Text('思考中...',
                              style: TextStyle(color: Colors.grey)),
                        ],
                      ),
                    );
                  }
                  final m = _messages[i];
                  final isUser = m['role'] == 'user';
                  return Align(
                    alignment: isUser
                        ? Alignment.centerRight
                        : Alignment.centerLeft,
                    child: Container(
                      constraints: const BoxConstraints(maxWidth: 280),
                      margin: const EdgeInsets.symmetric(vertical: 4),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: isUser
                            ? const Color(0xFF00D4FF).withValues(alpha: 0.15)
                            : const Color(0xFF1E293B),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(m['content'] ?? '',
                          style:
                              const TextStyle(fontSize: 14, height: 1.5)),
                    ),
                  );
                },
              ),
            ),
            // Input
            Padding(
              padding: const EdgeInsets.all(10),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _msgCtrl,
                      decoration: InputDecoration(
                        hintText: current != null
                            ? '向 ${current['name']} 提问...'
                            : '输入消息...',
                        border: const OutlineInputBorder(),
                        contentPadding: const EdgeInsets.symmetric(
                            horizontal: 14, vertical: 10),
                      ),
                      onSubmitted: (_) => _send(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: const Icon(Icons.send, color: Color(0xFF00D4FF)),
                    onPressed: _loading ? null : _send,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
