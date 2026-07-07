"""公共工具函数"""

import hashlib
import re
from typing import Any


def hash_content(content: str) -> str:
    """内容哈希 (用于去重)"""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除不安全字符"""
    return re.sub(r"[^\w\-_.]", "_", filename)


def chunk_list(lst: list[Any], size: int) -> list[list[Any]]:
    """将列表按 size 分块"""
    return [lst[i : i + size] for i in range(0, len(lst), size)]


def estimate_token_count(text: str) -> int:
    """
    粗略估算 token 数量 (中文按字，英文按 4 字符 ≈ 1 token)
    生产环境应替换为 tiktoken 精确计数
    """
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    english_chars = len(text) - chinese_chars
    return chinese_chars + english_chars // 4
