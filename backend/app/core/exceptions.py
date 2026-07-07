"""
全局异常处理器。

统一返回格式:
    {
        "error": {
            "code": "RESOURCE_NOT_FOUND",
            "message": "用户不存在",
            "request_id": "abc12345"
        }
    }
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("opc.exceptions")


# ========== 业务异常基类 ==========
class AppException(Exception):
    """应用级异常基类"""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Any = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


# ========== 常用业务异常 ==========
class NotFoundException(AppException):
    def __init__(self, message: str = "资源不存在", code: str = "NOT_FOUND"):
        super().__init__(message=message, code=code, status_code=404)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "未授权", code: str = "UNAUTHORIZED"):
        super().__init__(message=message, code=code, status_code=401)


class ForbiddenException(AppException):
    def __init__(self, message: str = "无权限", code: str = "FORBIDDEN"):
        super().__init__(message=message, code=code, status_code=403)


class ValidationException(AppException):
    def __init__(self, message: str = "参数错误", code: str = "VALIDATION_ERROR"):
        super().__init__(message=message, code=code, status_code=422)


class ConflictException(AppException):
    def __init__(self, message: str = "资源冲突", code: str = "CONFLICT"):
        super().__init__(message=message, code=code, status_code=409)


class TenantIsolationException(AppException):
    """租户隔离异常 —— 尝试跨租户访问"""

    def __init__(self, message: str = "跨租户访问被拒绝"):
        super().__init__(
            message=message,
            code="TENANT_ISOLATION_VIOLATION",
            status_code=403,
        )


# ========== Error Response Schema ==========
class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: Any = None


# ========== 注册异常处理器 ==========
def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        rid = getattr(request.state, "request_id", None)
        logger.warning(
            f"[{rid}] AppException: {exc.code} | {exc.message}",
            extra={"details": exc.details},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": ErrorResponse(
                    code=exc.code,
                    message=exc.message,
                    request_id=rid,
                    details=exc.details,
                ).model_dump()
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        rid = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": ErrorResponse(
                    code="VALIDATION_ERROR",
                    message="请求参数校验失败",
                    request_id=rid,
                    details=exc.errors(),
                ).model_dump()
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", None)
        logger.exception(f"[{rid}] Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": ErrorResponse(
                    code="INTERNAL_ERROR",
                    message="服务器内部错误",
                    request_id=rid,
                ).model_dump()
            },
        )
