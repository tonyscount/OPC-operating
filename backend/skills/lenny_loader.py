"""
Lenny Skills 加载器 — 将 86 个 Markdown 技能注册到 OPC Skill 系统。

扫描 lenny-skills-main/skills/*/SKILL.md，解析 YAML frontmatter，
为每个技能创建 LLM 驱动的 handler。

用法:
    from skills.lenny_loader import load_lenny_skills
    count = await load_lenny_skills()

    或启动时自动加载 (在 config.py 中配置):
    LENNY_SKILLS_PATH = "lenny-skills-main/skills"
"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from app.modules.skill.registry import skill_registry

logger = logging.getLogger("opc.skill.lenny")

# ========== 默认路径 (相对于项目根目录) ==========
DEFAULT_LENNY_PATH = Path(__file__).resolve().parent.parent.parent / "lenny-skills-main" / "skills"


def parse_skill_md(file_path: Path) -> dict[str, Any] | None:
    """
    解析 SKILL.md 文件，提取 frontmatter 和 body。

    返回:
        {
            "name": "writing-prds",
            "description": "Help users write effective PRDs...",
            "body": "... (完整的 Markdown 内容) ..."
        }
    """
    content = file_path.read_text(encoding="utf-8")

    # 解析 YAML frontmatter
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
    if not match:
        logger.warning(f"No frontmatter found in {file_path}")
        return None

    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        logger.warning(f"Invalid YAML frontmatter in {file_path}: {e}")
        return None

    body = match.group(2).strip()

    name = frontmatter.get("name", file_path.parent.name)
    description = frontmatter.get("description", f"Lenny Skill: {name}")

    return {"name": name, "description": description, "body": body}


def build_lenny_handler(skill_body: str, skill_name: str):
    """
    为 Lenny Skill 创建一个 LLM 驱动的 handler。

    Lenny Skills 没有可执行代码，而是通过 LLM 读取 Markdown 指令来工作。
    这个 handler 返回 skill 的完整内容，供 Agent 在执行时参考。
    """

    async def handler(params: dict, context: dict) -> dict:
        """
        Lenny Skill handler — 返回技能知识供 LLM 使用。

        params 可以包含:
          - topic: 用户关心的具体话题 (用于定位相关章节)
          - action: 用户想要的操作 (如 "write", "review", "analyze")
        """
        topic = params.get("topic", "")
        action = params.get("action", "help")

        # 提取相关章节
        sections = _extract_sections(skill_body, topic)

        return {
            "skill_name": skill_name,
            "action": action,
            "topic": topic,
            "guidance": {
                "principles": sections.get("Core Principles", "")[:2000],
                "questions": sections.get("Questions to Help Users", ""),
                "mistakes": sections.get("Common Mistakes to Flag", ""),
                "related": sections.get("Related Skills", ""),
            },
            "full_body": skill_body[:5000],  # 截断过长内容
            "instruction": (
                f"请基于 {skill_name} 技能的专业知识来帮助用户。"
                f"遵循其中的核心原则、诊断问题框架和常见错误警示。"
            ),
        }

    return handler


def _extract_sections(body: str, topic: str = "") -> dict[str, str]:
    """提取 Markdown body 中与 topic 相关的章节"""
    sections: dict[str, str] = {}
    current_section = "_preamble"
    current_content: list[str] = []

    for line in body.split("\n"):
        if line.startswith("## "):
            if current_content:
                sections[current_section] = "\n".join(current_content)
            current_section = line[3:].strip()
            current_content = []
        else:
            current_content.append(line)

    if current_content:
        sections[current_section] = "\n".join(current_content)

    # 如果有 topic，过滤相关章节
    if topic:
        relevant = {}
        for section_name, content in sections.items():
            if topic.lower() in section_name.lower() or topic.lower() in content.lower():
                relevant[section_name] = content
        if relevant:
            return relevant

    return sections


async def load_lenny_skills(skills_path: str | Path | None = None) -> int:
    """
    扫描 lenny-skills 目录，将所有 Markdown Skill 注册到 skill_registry。

    返回: 加载的技能数量
    """
    path = Path(skills_path) if skills_path else DEFAULT_LENNY_PATH

    if not path.exists():
        logger.warning(f"Lenny skills path not found: {path}")
        return 0

    loaded = 0
    for skill_dir in sorted(path.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        parsed = parse_skill_md(skill_md)
        if not parsed:
            continue

        name = parsed["name"]
        description = parsed["description"]
        body = parsed["body"]

        # 注册到 OPC Skill 系统
        try:
            skill_registry.register(
                name=f"lenny:{name}",
                display_name=f"📋 {name.replace('-', ' ').title()}",
                description=f"[Lenny's Podcast] {description}",
                parameters_schema={
                    "topic": {
                        "type": "string",
                        "description": "具体话题或问题方向",
                        "required": False,
                    },
                    "action": {
                        "type": "string",
                        "description": "操作类型: help/write/review/analyze/plan",
                        "required": False,
                        "default": "help",
                    },
                },
                timeout=30,
                required_permissions=[],
                is_builtin=True,
            )(build_lenny_handler(body, name))

            loaded += 1
        except Exception as e:
            logger.error(f"Failed to register lenny skill '{name}': {e}")

    logger.info(f"Loaded {loaded} lenny skills from {path}")
    return loaded


# ========== 便捷函数 ==========
def list_lenny_skill_names(skills_path: str | Path | None = None) -> list[str]:
    """列出所有可用的 Lenny Skill 名称 (不注册)"""
    path = Path(skills_path) if skills_path else DEFAULT_LENNY_PATH
    if not path.exists():
        return []

    names = []
    for skill_dir in sorted(path.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            names.append(skill_dir.name)
    return names
