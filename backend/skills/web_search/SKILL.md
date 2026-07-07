# web_search

## 描述
搜索互联网获取外部信息。当用户询问最新资讯、行业趋势、实时数据等内部知识库无法回答的问题时使用。

## 参数
- `query` (string, required): 搜索关键词
- `max_results` (integer, optional): 最大返回结果数，默认5

## 返回
```json
{
  "results": [
    {
      "title": "结果标题",
      "snippet": "摘要",
      "url": "链接"
    }
  ],
  "total": 5
}
```

## 使用场景
- 用户问"最近社群运营有什么新趋势"
- 用户问"帮我查一下XX政策的最新变化"
- 知识库没有覆盖的外部信息查询
