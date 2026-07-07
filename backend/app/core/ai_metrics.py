"""
AI 可观测性 — 追踪每次 LLM 调用的 token 消耗、耗时、成本
"""

import time
from collections import defaultdict

# 定价 (RMB/1M tokens)
MODEL_PRICES = {
    "deepseek-chat":       {"input": 1,  "output": 2},
    "deepseek-v4-pro":     {"input": 2,  "output": 8},
    "deepseek-v4-flash":   {"input": 0.5,"output": 2},
    "gpt-4o":              {"input": 5,  "output": 15},
    "gpt-4o-mini":         {"input": 0.15,"output": 0.6},
    "qwen-plus":           {"input": 2,  "output": 6},
    "default":             {"input": 1,  "output": 2},
}


class AIMetrics:
    """全局 AI 调用指标"""

    def __init__(self):
        self.calls: list[dict] = []
        self.session: dict = {
            "total_tokens": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_rmb": 0.0,
            "call_count": 0,
        }

    def record(self, model: str, input_tokens: int, output_tokens: int, duration_ms: float):
        """记录一次 LLM 调用"""
        prices = MODEL_PRICES.get(model, MODEL_PRICES["default"])
        cost = (input_tokens / 1_000_000) * prices["input"] + (output_tokens / 1_000_000) * prices["output"]

        call = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration_ms": round(duration_ms, 1),
            "cost_rmb": round(cost, 6),
            "timestamp": time.time(),
        }
        self.calls.append(call)
        if len(self.calls) > 1000:
            self.calls = self.calls[-500:]

        self.session["total_tokens"] += input_tokens + output_tokens
        self.session["total_input_tokens"] += input_tokens
        self.session["total_output_tokens"] += output_tokens
        self.session["total_cost_rmb"] += cost
        self.session["call_count"] += 1

    def get_session_stats(self) -> dict:
        return dict(self.session)

    def get_recent_calls(self, limit: int = 20) -> list[dict]:
        return self.calls[-limit:]


metrics = AIMetrics()
