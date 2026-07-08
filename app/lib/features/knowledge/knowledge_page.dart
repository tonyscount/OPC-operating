import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../../core/api/dio_client.dart';

class KnowledgePage extends StatefulWidget {
  const KnowledgePage({super.key});
  @override
  State<KnowledgePage> createState() => _KnowledgePageState();
}

class _KnowledgePageState extends State<KnowledgePage> {
  List _docs = [];
  bool _loading = true;
  final _questionCtrl = TextEditingController();
  String _answer = '';

  @override
  void initState() {
    super.initState();
    _loadDocs();
  }

  Future<void> _loadDocs() async {
    try {
      final resp = await ApiClient.instance
          .get('/knowledge/documents', params: {'page_size': '30'});
      setState(() {
        _docs = resp.data['items'] ?? [];
        _loading = false;
      });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  Future<void> _ask() async {
    final q = _questionCtrl.text.trim();
    if (q.isEmpty) return;
    setState(() => _answer = '思考中...');
    try {
      final fd = FormData();
      fd.fields.add(MapEntry('question', q));
      fd.fields.add(MapEntry('top_k', '5'));
      final resp = await Dio().post(
        '${ApiClient.baseUrl}/knowledge/ask',
        data: fd,
        options: Options(headers: {
          'Authorization':
              'Bearer ${await ApiClient.instance.accessToken}',
        }),
      );
      setState(() {
        _answer = resp.data['answer'] ?? '暂无法回答';
      });
    } catch (e) {
      setState(() => _answer = '查询失败: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B1120),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: Row(
                children: [
                  Text('知识库',
                      style: Theme.of(context)
                          .textTheme
                          .titleMedium
                          ?.copyWith(fontWeight: FontWeight.w700)),
                  const Spacer(),
                  Text('${_docs.length} 篇文档',
                      style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ),
            // Ask
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _questionCtrl,
                      decoration: const InputDecoration(
                        hintText: '问 AI 任何关于知识库的问题...',
                        border: OutlineInputBorder(),
                        contentPadding:
                            EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: const Icon(Icons.send, color: Color(0xFF00D4FF)),
                    onPressed: _ask,
                  ),
                ],
              ),
            ),
            if (_answer.isNotEmpty)
              Container(
                width: double.infinity,
                margin: const EdgeInsets.all(12),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: const Color(0xFF00D4FF).withOpacity(0.08),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(_answer,
                    style: const TextStyle(fontSize: 14, height: 1.6)),
              ),
            const Divider(height: 1, color: Color(0xFF1E293B)),
            // Doc list
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _docs.isEmpty
                      ? const Center(
                          child: Text('暂无文档，上传你的第一条知识',
                              style: TextStyle(color: Colors.grey)))
                      : RefreshIndicator(
                          onRefresh: _loadDocs,
                          child: ListView.builder(
                            itemCount: _docs.length,
                            padding: const EdgeInsets.only(bottom: 80),
                            itemBuilder: (_, i) {
                              final d = _docs[i];
                              return ListTile(
                                title: Text(d['title'] ?? '',
                                    style: const TextStyle(
                                        fontWeight: FontWeight.w600)),
                                subtitle: Text(
                                    '${d['file_type'] ?? ''} · ${d['status'] ?? ''} · ${d['chunk_count'] ?? 0} chunks'),
                                trailing: const Icon(Icons.chevron_right,
                                    color: Colors.grey),
                                onTap: () {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(
                                        content: Text(d['title'] ?? '')),
                                  );
                                },
                              );
                            },
                          ),
                        ),
            ),
          ],
        ),
      ),
    );
  }
}


