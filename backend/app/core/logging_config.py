"""
集中日志配置 — 统一管理所有模块的日志格式、输出、级别。

日志层级:
  opc                      ← 根 Logger
  ├── opc.middleware       ← 请求日志
  ├── opc.tenant           ← 租户安全网
  ├── opc.agent.*          ← Agent 编排/StopHook/Audit/Guardrails
  ├── opc.skill.*          ← Skill 注册/执行
  ├── opc.knowledge.*      ← 知识库/嵌入/检索
  ├── opc.search           ← 搜索
  └── opc.websocket        ← WebSocket

输出目标:
  1. 控制台 (stdout) — 开发环境彩色输出
  2. 文件 (logs/app.log) — 每小时轮转，保留 30 天
  3. 文件 (logs/error.log) — 仅 ERROR 级别，单独存储
  4. (可选) 飞书 Webhook — 生产环境 ERROR 告警
"""

import logging
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path

from app.config import settings

# ========== 日志格式 ==========

CONSOLE_FORMAT = (
    "%(asctime)s.%(msecs)03d | "
    "%(levelname)-5s | "
    "%(name)s | "
    "%(message)s"
)

CONSOLE_DATE_FORMAT = "%H:%M:%S"

FILE_FORMAT = (
    "%(asctime)s | "
    "%(levelname)-8s | "
    "%(name)-25s | "
    "%(funcName)-20s | "
    "%(message)s"
)

# 开发环境彩色格式 (仅控制台)
if settings.APP_ENV == "development":
    CONSOLE_FORMAT = (
        "\033[90m%(asctime)s\033[0m | "
        "%(levelcolor)s%(levelname)-5s\033[0m | "
        "\033[36m%(name)s\033[0m | "
        "%(message)s"
    )


class ColoredFormatter(logging.Formatter):
    """开发环境带颜色的日志格式化器"""
    COLORS = {
        "DEBUG": "\033[90m",     # 灰色
        "INFO": "\033[92m",      # 绿色
        "WARNING": "\033[93m",   # 黄色
        "ERROR": "\033[91m",     # 红色
        "CRITICAL": "\033[95m",  # 紫色
    }

    def format(self, record):
        record.levelcolor = self.COLORS.get(record.levelname, "")
        return super().format(record)


def setup_logging() -> None:
    """
    初始化全局日志系统。

    在 main.py 的 lifespan 中最先调用:
        from app.core.logging_config import setup_logging
        setup_logging()
    """
    root_logger = logging.getLogger("opc")
    root_logger.setLevel(logging.DEBUG if settings.APP_DEBUG else logging.INFO)

    # 清除已有的 handler (避免重复)
    root_logger.handlers.clear()

    # ===== 1. 控制台输出 =====
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if settings.APP_DEBUG else logging.INFO)

    if settings.APP_ENV == "development":
        console_handler.setFormatter(ColoredFormatter(CONSOLE_FORMAT, datefmt=CONSOLE_DATE_FORMAT))
    else:
        console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT, datefmt=CONSOLE_DATE_FORMAT))

    root_logger.addHandler(console_handler)

    # ===== 2. 文件输出 (全量日志, 按小时轮转) =====
    log_dir = Path(settings.BASE_DIR) / "logs"
    log_dir.mkdir(exist_ok=True)

    file_handler = TimedRotatingFileHandler(
        filename=log_dir / "app.log",
        when="H",
        interval=1,
        backupCount=24 * 30,  # 保留 30 天
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    root_logger.addHandler(file_handler)

    # ===== 3. 错误独立文件 =====
    error_handler = TimedRotatingFileHandler(
        filename=log_dir / "error.log",
        when="D",
        interval=1,
        backupCount=90,  # 保留 90 天
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    root_logger.addHandler(error_handler)

    # ===== 4. 飞书告警 (生产环境 ERROR) =====
    if settings.APP_ENV == "production" and settings.FEISHU_WEBHOOK_URL:
        feishu_handler = FeishuAlertHandler(settings.FEISHU_WEBHOOK_URL)
        feishu_handler.setLevel(logging.ERROR)
        root_logger.addHandler(feishu_handler)

    # ===== 抑制第三方库的 DEBUG 日志 =====
    for lib in ["sqlalchemy.engine", "httpx", "openai", "urllib3", "asyncio"]:
        logging.getLogger(lib).setLevel(logging.WARNING)

    # 写一条启动日志
    root_logger.info(
        f"Logging initialized | env={settings.APP_ENV} "
        f"| console={'DEBUG' if settings.APP_DEBUG else 'INFO'} "
        f"| file={log_dir / 'app.log'}"
    )


class FeishuAlertHandler(logging.Handler):
    """飞书 Webhook 告警处理器 — 仅 ERROR 及以上"""

    def __init__(self, webhook_url: str):
        super().__init__()
        self.webhook_url = webhook_url

    def emit(self, record: logging.LogRecord):
        try:
            import json
            import urllib.request

            msg = self.format(record)
            payload = json.dumps({
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": f"🚨 OPC {record.levelname}"},
                        "template": "red",
                    },
                    "elements": [
                        {"tag": "markdown", "content": f"**Module:** {record.name}\n**Time:** {record.asctime}\n```\n{msg[:1000]}\n```"},
                    ],
                },
            }).encode("utf-8")

            req = urllib.request.Request(
                self.webhook_url, data=payload,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # 飞书通知失败不影响主流程
