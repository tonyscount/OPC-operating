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
  bool _loading = false;
  String _selectedAgent = 'analyst';
  final _agents = [
    {'name': 'analyst', 'label': '分析师'},
    {'name': 'support_agent', 'label': '支持'},
    {'name': 'reviewer', 'label': '审查'},
    {'name': 'judge', 'label': '裁判'},
  ];

  Future<void> _send() async {
    final text = _msgCtrl.text.trim();
    if (text.isEmpty) return;

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
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B1120),
      body: SafeArea(
        child: Column(
          children: [
            // Header + agent selector
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: Row(
                children: [
                  const Text('AI Agent',
                      style: TextStyle(
                          fontSize: 16, fontWeight: FontWeight.w700)),
                  const SizedBox(width: 12),
                  ..._agents.map((a) => Padding(
                        padding: const EdgeInsets.only(right: 4),
                        child: ChoiceChip(
                          label: Text(a['label']!,
                              style: TextStyle(
                                  fontSize: 11,
                                  color: _selectedAgent == a['name']
                                      ? Colors.black
                                      : Colors.white70)),
                          selected: _selectedAgent == a['name'],
                          selectedColor: const Color(0xFF00D4FF),
                          onSelected: (_) =>
                              setState(() => _selectedAgent = a['name']!),
                        ),
                      )),
                ],
              ),
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
                    alignment:
                        isUser ? Alignment.centerRight : Alignment.centerLeft,
                    child: Container(
                      constraints: const BoxConstraints(maxWidth: 280),
                      margin: const EdgeInsets.symmetric(vertical: 4),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: isUser
                            ? const Color(0xFF00D4FF).withOpacity(0.15)
                            : const Color(0xFF1E293B),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(m['content'] ?? '',
                          style: const TextStyle(
                              fontSize: 14, height: 1.5)),
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
                      decoration: const InputDecoration(
                        hintText: '输入消息...',
                        border: OutlineInputBorder(),
                        contentPadding: EdgeInsets.symmetric(
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
