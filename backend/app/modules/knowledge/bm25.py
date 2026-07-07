"""
轻量 BM25 关键词检索 — 零外部依赖

与 ChromaDB 向量检索并行执行，结果合并去重排序。
"""

import math
import re
from collections import defaultdict


class BM25:
    """BM25 关键词检索器"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: list[str] = []
        self.doc_metas: list[dict] = []
        self.tokenized: list[list[str]] = []
        self.doc_len: list[int] = []
        self.avgdl: float = 0.0
        self.idf: dict[str, float] = {}
        self._fitted = False

    def fit(self, documents: list[str], metas: list[dict] | None = None):
        """索引文档"""
        self.documents = documents
        self.doc_metas = metas or [{}] * len(documents)
        self.tokenized = [self._tokenize(d) for d in documents]
        self.doc_len = [len(t) for t in self.tokenized]
        self.avgdl = sum(self.doc_len) / max(len(documents), 1)
        self._compute_idf()
        self._fitted = True

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """搜索，返回带分数的结果"""
        if not self._fitted:
            return []

        query_tokens = self._tokenize(query)
        scores = []

        for i, doc_tokens in enumerate(self.tokenized):
            score = 0.0
            doc_len = self.doc_len[i]
            term_freqs = defaultdict(int)
            for t in doc_tokens:
                term_freqs[t] += 1

            for token in query_tokens:
                if token not in self.idf:
                    continue
                tf = term_freqs.get(token, 0)
                if tf == 0:
                    continue
                idf_val = self.idf[token]
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avgdl, 1))
                score += idf_val * numerator / max(denominator, 0.001)

            if score > 0:
                scores.append({
                    "index": i,
                    "score": round(score, 4),
                    "content": self.documents[i][:500],
                    "meta": self.doc_metas[i],
                    "source": "bm25",
                })

        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]

    def _tokenize(self, text: str) -> list[str]:
        """中文按字分词，英文按空格分词"""
        tokens = []
        # 中文单字
        chinese = re.findall(r"[一-鿿]", text)
        tokens.extend(chinese)
        # 英文单词
        english = re.findall(r"[a-zA-Z0-9]+", text.lower())
        tokens.extend(english)
        # 2-gram for Chinese
        for i in range(len(chinese) - 1):
            tokens.append(chinese[i] + chinese[i + 1])
        return tokens

    def _compute_idf(self):
        """计算 IDF"""
        N = len(self.tokenized)
        df = defaultdict(int)
        for tokens in self.tokenized:
            for token in set(tokens):
                df[token] += 1
        self.idf = {
            token: math.log((N - freq + 0.5) / (freq + 0.5) + 1.0)
            for token, freq in df.items()
        }


def merge_results(vector_results: list[dict], bm25_results: list[dict],
                  vector_weight: float = 0.6, top_k: int = 5) -> list[dict]:
    """
    合并向量检索和 BM25 结果，去重 + Reranker 重排序。

    策略:
      1. 去重 (相同 document_id 合并，取最高分)
      2. Reranker: 标题关键词匹配加权
      3. 交叉验证: 向量+BM25 同时命中 → 额外加分
    """
    # Step 1: 合并去重
    by_doc = {}
    for r in vector_results:
        doc_id = r.get("document_id", r.get("id", ""))
        score = r.get("score", 0.5)
        if doc_id not in by_doc or score > by_doc[doc_id]["score"]:
            by_doc[doc_id] = {**r, "match_type": "semantic", "source": "vector"}

    for r in bm25_results:
        doc_id = r.get("meta", {}).get("document_id", str(r.get("index", "")))
        # BM25 分数归一化 (score 通常远大于 1)
        score = min(r.get("score", 1) / 10, 1.0)
        if doc_id not in by_doc:
            by_doc[doc_id] = {
                "id": f"bm25-{r['index']}",
                "content": r["content"][:500],
                "document_title": r.get("meta", {}).get("document_title", ""),
                "document_id": doc_id,
                "score": score,
                "match_type": "keyword",
                "source": "bm25",
            }
        else:
            # 向量+BM25 双命中 → 交叉验证加分
            by_doc[doc_id]["score"] = max(by_doc[doc_id]["score"], score) + 0.15
            by_doc[doc_id]["cross_hit"] = True

    # Step 2: Reranker — 标题匹配加权
    # (在 search_knowledge 调用时传入 query 进行标题打分)
    merged = list(by_doc.values())
    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged[:top_k]

def rerank_with_query(results: list[dict], query: str) -> list[dict]:
    """
    基于 query 对结果重排序 — 标题关键词匹配加权。
    轻量 Reranker，零依赖，适合本地部署。
    """
    query_lower = query.lower()
    query_terms = set(query_lower.split())

    for r in results:
        bonus = 0
        title = (r.get("document_title", "")).lower()
        content = (r.get("content", "")).lower()

        # 标题精确匹配
        if query_lower in title:
            bonus += 0.3
        # 标题关键词命中
        title_hits = sum(1 for t in query_terms if t in title)
        bonus += title_hits * 0.08
        # 内容关键词命中
        content_hits = sum(1 for t in query_terms if t in content)
        bonus += content_hits * 0.03
        # 交叉验证加分
        if r.get("cross_hit"):
            bonus += 0.1

        r["original_score"] = r.get("score", 0)
        r["score"] = min(r.get("score", 0) + bonus, 1.0)
        r["rerank_bonus"] = round(bonus, 3)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
