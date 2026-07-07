@echo off
REM OPC Platform — PostgreSQL 备份 (Windows)
REM 用法: backup.bat
REM 输出: backups\opc_backup_YYYY-MM-DD_HHMMSS.sql.gz

setlocal enabledelayedexpansion

set BACKUP_DIR=%~dp0..\backups
set TIMESTAMP=%date:~0,10%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set FILE=%BACKUP_DIR%\opc_backup_%TIMESTAMP%.sql

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

echo [%TIME%] Starting backup...

REM 使用 pg_dump (需在 PATH 中)
set PGPASSWORD=opc_dev_password
pg_dump -U opc_user -h localhost -d opc_platform --no-owner --no-acl > "%FILE%" 2>nul

if %ERRORLEVEL% EQU 0 (
    REM 压缩
    powershell -Command "Compress-Archive -Path '%FILE%' -DestinationPath '%FILE%.zip' -Force" 2>nul
    del "%FILE%" 2>nul
    echo [%TIME%] Backup OK: %FILE%.zip (%FILE%.zip size)
) else (
    echo [%TIME%] Backup FAILED
    exit /b 1
)

REM 清理 7 天前的备份
forfiles /p "%BACKUP_DIR%" /m "opc_backup_*.zip" /d -7 /c "cmd /c del @file" 2>nul

echo [%TIME%] Cleanup complete
exit /b 0
