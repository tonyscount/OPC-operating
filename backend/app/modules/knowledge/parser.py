"""
文档解析器 — 支持 PDF / Markdown / TXT / DOCX

处理流程:
  1. 根据文件类型调用对应解析器
  2. 提取纯文本
  3. 按指定策略分块 (段落/滑动窗口/固定大小)
  4. 返回清洗后的文本块列表
"""

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path


@dataclass
class ChunkResult:
    content: str
    chunk_index: int
    token_count: int  # 估算
    metadata: dict  # page/section/source


class DocumentParser:
    """文档解析 & 分块引擎"""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def parse(self, file_path: str, file_type: str) -> str:
        """提取文档纯文本"""
        if file_type == "txt":
            return self._parse_txt(file_path)
        elif file_type == "md":
            return self._parse_markdown(file_path)
        elif file_type == "pdf":
            return self._parse_pdf(file_path)
        elif file_type == "docx":
            return self._parse_docx(file_path)
        else:
            raise ValueError(f"不支持的文件类型: {file_type}")

    def chunk(self, text: str, file_type: str = "txt") -> list[ChunkResult]:
        """将文本分块"""
        # 按段落分割
        paragraphs = self._split_paragraphs(text)

        # 合并短段落、拆分长段落
        chunks: list[ChunkResult] = []
        current = ""
        idx = 0

        for para in paragraphs:
            para = self._clean_text(para)
            if not para:
                continue

            # 如果当前块 + 新段落 > chunk_size，先保存当前块
            if self._estimate_tokens(current + para) > self.chunk_size and current:
                chunks.append(ChunkResult(
                    content=current.strip(),
                    chunk_index=idx,
                    token_count=self._estimate_tokens(current.strip()),
                    metadata={"source": file_type},
                ))
                idx += 1
                # 重叠: 保留最后若干字符
                overlap_text = current[-self.chunk_overlap * 4:] if self.chunk_overlap > 0 else ""
                current = overlap_text + para
            else:
                current = (current + "\n\n" + para).strip() if current else para

        # 保存最后一块
        if current.strip():
            chunks.append(ChunkResult(
                content=current.strip(),
                chunk_index=idx,
                token_count=self._estimate_tokens(current.strip()),
                metadata={"source": file_type},
            ))

        return chunks

    # ========== 解析器实现 ==========

    def _parse_txt(self, path: str) -> str:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _parse_markdown(self, path: str) -> str:
        """Markdown: 移除部分格式但保留结构"""
        text = self._parse_txt(path)
        # 去掉代码块标记但保留代码
        text = re.sub(r"```\w*\n", "", text)
        text = text.replace("```", "")
        # 去掉图片语法但保留 alt text
        text = re.sub(r"!\[(.*?)\]\(.*?\)", r"\1", text)
        # 链接保留文字
        text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
        # 去掉多余空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    def _parse_pdf(self, path: str) -> str:
        """PDF 解析 (使用 pypdf2)"""
        try:
            from pypdf2 import PdfReader
        except ImportError:
            raise ImportError("请安装 pypdf2: pip install pypdf2")

        reader = PdfReader(path)
        pages = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            # 标注页码
            pages.append(f"[Page {i + 1}]\n{page_text}")

        return "\n\n".join(pages)

    def _parse_docx(self, path: str) -> str:
        """DOCX 解析"""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("请安装 python-docx: pip install python-docx")

        doc = Document(path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)

    # ========== 辅助方法 ==========

    def _split_paragraphs(self, text: str) -> list[str]:
        """按段落分割"""
        # 按双换行分割
        parts = re.split(r"\n\s*\n", text)
        return [p for p in parts if p.strip()]

    def _clean_text(self, text: str) -> str:
        """清洗文本"""
        # 移除控制字符
        text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)
        # 压缩多余空白
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _estimate_tokens(self, text: str) -> int:
        """
        粗略估算 token 数。
        中文: 按字符数; 英文: 按 4 字符 ≈ 1 token
        """
        chinese = len(re.findall(r"[一-鿿]", text))
        others = len(text) - chinese
        return chinese + max(1, others // 4)


# ========== 全局单例 ==========
parser = DocumentParser()
