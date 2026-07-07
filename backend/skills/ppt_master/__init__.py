"""
PPT Master Skill — AI 驱动的原生可编辑 PPTX 生成

管线: 源文档 → Markdown → 策略师 → 执行器 → 质检 → PPTX 导出

集成到 OPC Skill 系统，可通过 Agent 或直接 API 调用。
"""

from app.modules.skill.registry import skill_registry
from .handler import generate_ppt


@skill_registry.register(
    name="ppt_master",
    display_name="PPT 制作大师",
    description=(
        "AI 驱动的 PPT 生成器，将主题和源材料（PDF/DOCX/URL/Markdown）"
        "转换为原生可编辑的 PPTX 文件。支持中英文，多风格可选。"
    ),
    parameters_schema={
        "topic": {
            "type": "string",
            "description": "PPT 主题，如「Q3 运营数据复盘」「OPC 平台技术架构介绍」",
            "required": True,
        },
        "source_files": {
            "type": "array",
            "description": "源材料文件路径列表 (PDF/DOCX/URL/Markdown)，可选",
            "default": [],
        },
        "template_format": {
            "type": "string",
            "description": "画布格式: ppt169 (16:9 宽屏) / ppt43 (4:3 标准)",
            "default": "ppt169",
        },
        "language": {
            "type": "string",
            "description": "输出语言: zh-CN / en",
            "default": "zh-CN",
        },
        "style": {
            "type": "string",
            "description": "设计风格: professional / creative / minimal / tech",
            "default": "professional",
        },
        "max_pages": {
            "type": "integer",
            "description": "最大页数",
            "default": 12,
        },
    },
    timeout=300,
    required_permissions=["skill:execute"],
    is_builtin=True,
)
async def ppt_master_handler(params: dict, context: dict) -> dict:
    """
    PPT 生成 Skill 入口。

    params: { topic, source_files?, template_format?, language?, style?, max_pages? }
    context: { user_id, tenant_id, trace_id }

    返回: { status, project_name, pptx_path, page_count }
    """
    return await generate_ppt(
        topic=params.get("topic", ""),
        source_files=params.get("source_files"),
        template_format=params.get("template_format", "ppt169"),
        language=params.get("language", "zh-CN"),
        style=params.get("style", "professional"),
        max_pages=int(params.get("max_pages", 12)),
        tenant_id=str(context.get("tenant_id", "")),
        user_id=str(context.get("user_id", "")),
    )
