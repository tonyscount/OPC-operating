"""
PPT Master Skill — AI 驱动的原生 PPTX 生成

将源文档 (PDF/DOCX/URL/Markdown) 通过多角色 AI 协作转换为可编辑的 PPTX。
管线: Source → Markdown → 策略师规划 → 图片生成 → 执行器 SVG → 质检 → 导出
"""

import logging
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.modules.agent.orchestrator import LLMClient
from app.config import settings

logger = logging.getLogger("opc.skill.ppt_master")

# PPT Master 项目根目录
PPT_MASTER_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "ppt-master-main"
SCRIPTS_DIR = PPT_MASTER_ROOT / "skills" / "ppt-master" / "scripts"
PROJECTS_DIR = PPT_MASTER_ROOT / "projects"


async def generate_ppt(
    *,
    topic: str,
    source_files: list[str] | None = None,
    template_format: str = "ppt169",
    language: str = "zh-CN",
    style: str = "professional",
    max_pages: int = 12,
    tenant_id: str = "",
    user_id: str = "",
) -> dict:
    """
    PPT 生成主入口。

    管线:
      1. 初始化项目
      2. 源材料转 Markdown
      3. AI 策略师生成大纲 (LLM)
      4. AI 执行器逐页生成 SVG (LLM)
      5. 质检 + 导出 PPTX
    """
    project_name = f"ppt_{uuid.uuid4().hex[:8]}"
    project_path = PROJECTS_DIR / project_name

    try:
        # ===== Step 1: 初始化项目 =====
        logger.info(f"[PPT Master] Creating project: {project_name}")
        result = _run_script("project_manager.py", [
            "init", str(project_path),
            "--format", template_format,
        ])
        # 脚本会加后缀: project_name → project_name_ppt169_YYYYMMDD
        # 从输出解析实际路径, 或扫描 projects 目录
        import re
        created_match = re.search(r'Project created: (.+)', result.stdout)
        if created_match:
            project_path = Path(created_match.group(1))
            project_name = project_path.name
        else:
            # 扫描找最新匹配的目录
            candidates = sorted(
                PROJECTS_DIR.glob(f"{project_path.name}_*"),
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
            if candidates:
                project_path = candidates[0]
                project_name = project_path.name

        # ===== Step 2: 源材料转换 =====
        if source_files:
            logger.info(f"[PPT Master] Importing sources: {source_files}")
            _run_script("source_to_md.py", [
                str(project_path / "sources"),
                *source_files,
            ])

        # ===== Step 3: AI 策略师生成大纲 =====
        outline = await _ai_generate_outline(
            topic=topic,
            language=language,
            style=style,
            max_pages=max_pages,
            source_dir=str(project_path / "sources") if source_files else None,
        )

        # 写 spec (策略师输出)
        spec_path = project_path / "design_spec.md"
        spec_path.write_text(outline, encoding="utf-8")
        logger.info(f"[PPT Master] Design spec written: {spec_path}")

        # ===== Step 4: AI 执行器生成 SVG =====
        svg_pages = await _ai_generate_svgs(
            design_spec=outline,
            project_path=str(project_path),
            language=language,
        )

        # 写 SVG 文件 (PPT Master 管线使用 svg_output 目录)
        svg_dir = project_path / "svg_output"
        svg_dir.mkdir(exist_ok=True)
        for i, svg in enumerate(svg_pages, 1):
            page_path = svg_dir / f"page_{i:03d}.svg"
            page_path.write_text(svg, encoding="utf-8")

        # ===== Step 5: 质检 + 后处理 =====
        _run_script("svg_quality_checker.py", [str(project_path)])
        _run_script("finalize_svg.py", [
            str(project_path),
            "--quiet",
        ])

        # ===== Step 6: 导出 PPTX =====
        export_dir = project_path / "exports"
        export_dir.mkdir(exist_ok=True)
        export_path = export_dir / f"{project_name}.pptx"
        _run_script("svg_to_pptx.py", [
            str(project_path),
            "-o", str(export_path),
            "-q",
        ])

        pptx_ready = export_path.exists()

        return {
            "status": "completed",
            "project_name": project_name,
            "project_path": str(project_path),
            "pptx_path": str(export_path) if pptx_ready else None,
            "page_count": len(svg_pages),
            "topic": topic,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.exception(f"[PPT Master] Pipeline failed: {e}")
        return {
            "status": "failed",
            "project_name": project_name,
            "project_path": str(project_path),
            "error": str(e),
        }


def _run_script(script_name: str, args: list[str]) -> subprocess.CompletedProcess:
    """执行 PPT Master 脚本"""
    script_path = SCRIPTS_DIR / script_name
    # Windows 用 python, Linux/Mac 用 python3
    py = "python" if os.name == "nt" else "python3"
    cmd = [py, str(script_path), *args]
    logger.info(f"[PPT Master] Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(PPT_MASTER_ROOT),
    )

    if result.returncode != 0:
        logger.warning(f"[PPT Master] Script error ({script_name}): {result.stderr[:500]}")
        raise RuntimeError(f"PPT Master 脚本失败: {script_name} — {result.stderr[:200]}")
    return result


# ============================================================
# AI 策略师 — 生成设计大纲
# ============================================================

STRATEGIST_SYSTEM = """你是 PPT 策略师。根据用户主题和源材料，生成一份结构化的演示文稿设计大纲。

输出格式必须是 Markdown，包含以下部分:

## 元信息
- title: 标题
- subtitle: 副标题
- language: 语言
- total_pages: 总页数

## 页面规划
逐页列出:
- page_N: 页面标题 | 布局类型 (title_slide/content/two_column/image_full/chart/comparison/quote/ending) | 内容要点

## 设计规范
- 主色: HEX
- 辅色: HEX
- 字体: 中文字体 + 英文字体
- 风格关键词: 3-5 个

要求:
- 每页内容要具体，不能只有标题
- 布局类型必须从给定选项中选
- 总页数不超过 max_pages
- 中英双语标注"""


async def _ai_generate_outline(
    topic: str,
    language: str,
    style: str,
    max_pages: int,
    source_dir: str | None,
) -> str:
    """使用 LLM 生成 PPT 设计大纲"""
    client = LLMClient(temperature=0.7)

    source_context = ""
    if source_dir:
        source_path = Path(source_dir)
        if source_path.exists():
            md_files = list(source_path.glob("*.md"))
            if md_files:
                # 限制上下文大小
                context_parts = []
                total_chars = 0
                for f in md_files[:5]:
                    text = f.read_text(encoding="utf-8")[:3000]
                    context_parts.append(f"## 源文件: {f.name}\n\n{text}")
                    total_chars += len(text)
                    if total_chars > 15000:
                        break
                source_context = "\n\n".join(context_parts)

    prompt = f"""为主题生成 PPT 设计大纲:

**主题**: {topic}
**语言**: {language}
**风格**: {style}
**最大页数**: {max_pages}

{"**参考材料**:\n" + source_context if source_context else "无参考材料，请根据主题创作。"}"""

    messages = [
        {"role": "system", "content": STRATEGIST_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        response = await client.chat(messages)
        return response.get("content", "") if isinstance(response, dict) else str(response)
    except Exception as e:
        logger.warning(f"[PPT Master] Strategist LLM failed: {e}, using fallback")
        return _fallback_outline(topic, language, max_pages)


# ============================================================
# AI 执行器 — 生成 SVG 页面
# ============================================================

EXECUTOR_SYSTEM = """你是 PPT 执行器，负责将设计大纲转化为 SVG 页面。

SVG 要求:
1. viewBox="0 0 1280 720" (16:9)
2. 纯手写 SVG，不使用 AI 图片生成
3. 使用现代设计元素: 渐变、圆角、卡片、阴影
4. 配色严格遵循设计规范中的主色和辅色
5. 内容文字清晰可读，字号不小于 14px
6. 每页 SVG 必须独立且完整
7. 包含 <style> 标签定义样式
8. 使用 <foreignObject> 处理长文本块

只输出 SVG 代码，不要解释。输出格式:
```svg
<svg ...>...</svg>
```"""


async def _ai_generate_svgs(
    design_spec: str,
    project_path: str,
    language: str,
) -> list[str]:
    """AI 执行器逐页生成 SVG"""
    client = LLMClient(temperature=0.5)

    # 解析页数
    import re
    pages = re.findall(r'page_\d+:', design_spec)
    total_pages = len(pages) or 8

    svg_pages = []
    for i in range(1, total_pages + 1):
        # 提取当前页的设计规范
        page_spec = _extract_page_spec(design_spec, i)

        prompt = f"""为以下页面设计生成 SVG:

{page_spec}

设计规范 (从 spec 中提取):
{_extract_design_tokens(design_spec)}"""

        messages = [
            {"role": "system", "content": EXECUTOR_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await client.chat(messages)
            text = response.get("content", "") if isinstance(response, dict) else str(response)
            svg = _extract_svg_from_response(text)
            if svg:
                svg_pages.append(svg)
                logger.info(f"[PPT Master] SVG page {i}/{total_pages} generated")
        except Exception as e:
            logger.error(f"[PPT Master] SVG page {i} failed: {e}")
            svg_pages.append(_placeholder_svg(i, design_spec))

    return svg_pages


def _extract_page_spec(spec: str, page_num: int) -> str:
    """从完整 spec 中提取单页描述"""
    import re
    pattern = rf'page_{page_num}:.*?(?=page_{page_num + 1}:|\Z)'
    match = re.search(pattern, spec, re.DOTALL)
    return match.group(0) if match else f"Page {page_num}"


def _extract_design_tokens(spec: str) -> str:
    """提取设计 Token"""
    import re
    tokens = []
    for key in ["主色", "辅色", "字体", "风格关键词"]:
        match = re.search(rf'{key}[：:]\s*(.+)', spec)
        if match:
            tokens.append(f"- {key}: {match.group(1)}")
    return "\n".join(tokens) if tokens else "- 主色: #1a1a2e\n- 辅色: #e94560"


def _extract_svg_from_response(text: str) -> str | None:
    """从 LLM 回复中提取 SVG 代码"""
    import re
    match = re.search(r'<svg[\s\S]*?</svg>', text, re.IGNORECASE)
    return match.group(0) if match else None


def _placeholder_svg(page_num: int, spec: str) -> str:
    """生成占位 SVG"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <rect width="1280" height="720" fill="#1a1a2e"/>
  <text x="640" y="360" text-anchor="middle" fill="#ffffff" font-size="32" font-family="sans-serif">
    Page {page_num}
  </text>
  <text x="640" y="420" text-anchor="middle" fill="#888" font-size="18" font-family="sans-serif">
    Content generation in progress...
  </text>
</svg>"""


def _fallback_outline(topic: str, language: str, max_pages: int) -> str:
    """LLM 不可用时的回退大纲"""
    return f"""## 元信息
- title: {topic}
- subtitle:
- language: {language}
- total_pages: {max_pages}

## 页面规划
""" + "\n".join([
    f"- page_{i}: 第{i}页 | content | 内容要点待补充"
    for i in range(1, max_pages + 1)
]) + """

## 设计规范
- 主色: #1a1a2e
- 辅色: #e94560
- 字体: Microsoft YaHei + Inter
- 风格关键词: professional clean modern
"""
