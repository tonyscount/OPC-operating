"""
数据库备份 — Celery 定时任务

每天凌晨 3:00 自动执行 pg_dump，保留最近 7 天。
每月 1 号的备份额外保留为 monthly 归档。
"""

import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from celery import shared_task

from app.config import settings

logger = logging.getLogger("opc.tasks.db_backup")

BACKUP_DIR = Path(__file__).resolve().parent.parent.parent.parent / "backups"
RETENTION_DAYS = 7


@shared_task(
    name="db_backup_daily",
    bind=True,
    max_retries=1,
    soft_time_limit=300,
    time_limit=600,
)
def db_backup_daily(self):
    """每日数据库备份 (pg_dump + gzip 压缩)"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d_%H%M%S")
    filename = f"opc_backup_{timestamp}.sql"
    filepath = BACKUP_DIR / filename

    # 解析数据库连接信息
    db_url = settings.DATABASE_URL_SYNC
    # 格式: postgresql://user:pass@host:port/dbname
    try:
        _, rest = db_url.split("://", 1)
        auth, rest = rest.split("@", 1)
        user, password = auth.split(":", 1)
        host_port, dbname = rest.split("/", 1)
        host = host_port.split(":")[0]
        port = host_port.split(":")[1] if ":" in host_port else "5432"
    except Exception:
        logger.error(f"Failed to parse DATABASE_URL: {db_url}")
        return {"status": "failed", "error": "Invalid DATABASE_URL"}

    env = os.environ.copy()
    env["PGPASSWORD"] = password

    try:
        # 执行 pg_dump
        cmd = [
            "pg_dump",
            "-U", user,
            "-h", host,
            "-p", port,
            "-d", dbname,
            "--no-owner",
            "--no-acl",
            "-f", str(filepath),
        ]
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=300
        )

        if result.returncode != 0:
            logger.error(f"pg_dump failed: {result.stderr[:500]}")
            # 清理失败文件
            if filepath.exists():
                filepath.unlink()
            return {"status": "failed", "error": result.stderr[:200]}

        # 压缩
        import gzip
        gz_path = filepath.with_suffix(".sql.gz")
        with open(filepath, "rb") as f_in:
            with gzip.open(gz_path, "wb") as f_out:
                f_out.writelines(f_in)
        filepath.unlink()  # 删除未压缩原文件

        size_kb = gz_path.stat().st_size // 1024
        logger.info(f"Backup created: {gz_path.name} ({size_kb}KB)")

        # 每月 1 号 → 永久存档
        if now.day == 1:
            monthly = BACKUP_DIR / f"monthly_{timestamp}.sql.gz"
            import shutil
            shutil.copy2(gz_path, monthly)
            logger.info(f"Monthly archive: {monthly.name}")

    except subprocess.TimeoutExpired:
        logger.error("pg_dump timed out")
        if filepath.exists():
            filepath.unlink()
        return {"status": "failed", "error": "Timeout"}

    except Exception as e:
        logger.exception("Backup failed")
        return {"status": "failed", "error": str(e)}

    # 清理过期备份
    _cleanup_old_backups()

    return {"status": "ok", "file": str(gz_path), "size_kb": size_kb}


def _cleanup_old_backups():
    """删除超过保留期的备份"""
    cutoff = datetime.now(timezone.utc).timestamp() - (RETENTION_DAYS * 86400)
    for f in BACKUP_DIR.glob("opc_backup_*.sql.gz"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            logger.info(f"Cleaned up old backup: {f.name}")
