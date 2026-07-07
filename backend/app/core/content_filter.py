"""
内容安全过滤引擎 — 三层防线

L1: 实时过滤 — 发帖/评论时扫描，命中拒绝
L2: 需审核标记 — 可疑内容标记 is_flagged，人工审核
L3: 用户举报 — 累积举报自动隐藏

词库: app/core/word_filter/sensitive_words.json (热加载)

用法:
    from app.core.content_filter import filter_content, FilterResult

    result = filter_content("这是帖子内容")
    if not result.allowed:
        raise ValidationException(result.reason)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

logger = logging.getLogger("opc.filter")

WORDBANK_PATH = Path(__file__).parent / "word_filter" / "sensitive_words.json"


@dataclass
class FilterResult:
    allowed: bool
    reason: str = ""
    flagged: bool = False       # 需人工审核
    matched_keywords: list[str] = field(default_factory=list)
    matched_patterns: list[str] = field(default_factory=list)


class ContentFilter:
    """敏感词过滤器 — 加载 JSON 词库，热更新"""

    _instance: ClassVar["ContentFilter | None"] = None
    _mtime: float = 0

    def __init__(self):
        self.block_keywords: list[str] = []
        self.block_patterns: dict[str, str] = {}
        self.review_keywords: list[str] = []
        self.spam_config: dict = {}
        self._load()

    @classmethod
    def get_instance(cls) -> "ContentFilter":
        """单例 + 热加载"""
        mtime = WORDBANK_PATH.stat().st_mtime if WORDBANK_PATH.exists() else 0
        if cls._instance is None or mtime > cls._mtime:
            cls._instance = ContentFilter()
            cls._mtime = mtime
        return cls._instance

    def _load(self):
        if not WORDBANK_PATH.exists():
            logger.warning(f"Word bank not found: {WORDBANK_PATH}")
            return
        with open(WORDBANK_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.block_keywords = data.get("block_keywords", [])
        self.block_patterns = data.get("block_patterns", {})
        self.review_keywords = data.get("review_keywords", [])
        self.spam_config = data.get("spam_patterns", {})
        logger.info(
            f"Filter loaded: {len(self.block_keywords)} block keywords, "
            f"{len(self.block_patterns)} patterns, "
            f"{len(self.review_keywords)} review keywords"
        )

    def check(self, content: str) -> FilterResult:
        """
        扫描内容，返回过滤结果。

        - 命中 block_keywords → allowed=False
        - 命中 block_patterns (手机/QQ/URL) → allowed=False
        - 命中 review_keywords → flagged=True, allowed=True
        - 内容过短/重复字符过多 → allowed=False
        """
        if not content or not content.strip():
            return FilterResult(allowed=False, reason="内容不能为空")

        text = content.strip()

        # ——— 垃圾检测 ———
        min_len = self.spam_config.get("min_content_length", 2)
        if len(text) < min_len:
            return FilterResult(allowed=False, reason=f"内容过短，至少 {min_len} 个字符")

        max_repeat = self.spam_config.get("max_repeat_chars", 5)
        if self._has_repeat_chars(text, max_repeat):
            return FilterResult(allowed=False, reason="内容含过多重复字符")

        # ——— 敏感词扫描 ———
        matched = []
        for kw in self.block_keywords:
            if kw.lower() in text.lower():
                matched.append(kw)

        if matched:
            return FilterResult(
                allowed=False,
                reason=f"内容包含敏感词: {', '.join(matched[:3])}",
                matched_keywords=matched,
            )

        # ——— 正则模式扫描 ———
        pattern_matched = []
        for name, pattern in self.block_patterns.items():
            if re.search(pattern, text):
                pattern_matched.append(name)

        if pattern_matched:
            names = {
                "phone": "手机号",
                "qq": "QQ号",
                "wechat": "微信号",
                "url_short": "外部链接",
            }
            cn = [names.get(p, p) for p in pattern_matched]
            return FilterResult(
                allowed=False,
                reason=f"内容包含联系方式: {', '.join(cn)}",
                matched_patterns=pattern_matched,
            )

        # ——— 需审核关键词 ———
        review_matched = []
        for kw in self.review_keywords:
            if kw in text:
                review_matched.append(kw)

        if review_matched:
            return FilterResult(
                allowed=True,
                flagged=True,
                reason=f"内容含需审核关键词: {', '.join(review_matched[:3])}",
                matched_keywords=review_matched,
            )

        return FilterResult(allowed=True)

    @staticmethod
    def _has_repeat_chars(text: str, threshold: int) -> bool:
        """检测连续重复字符 (如 '啊啊啊啊啊啊')"""
        if len(text) < threshold:
            return False
        count = 1
        for i in range(1, len(text)):
            if text[i] == text[i - 1]:
                count += 1
                if count >= threshold:
                    return True
            else:
                count = 1
        return False


# ============================================================
# 对外 API
# ============================================================

def filter_content(content: str) -> FilterResult:
    """便捷函数: 过滤文本内容"""
    return ContentFilter.get_instance().check(content)
