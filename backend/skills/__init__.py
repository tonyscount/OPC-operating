"""
Skill 实现目录

每个 Skill 是一个独立的 Python 文件，用 @skill_registry.register 装饰器注册。
Agent 通过 list_skills() 发现可用 Skill，LLM 根据描述自主选择调用。
"""
