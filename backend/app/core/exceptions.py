"""自定义异常 + FastAPI 异常处理器"""

from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    """应用基础异常"""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "INTERNAL_ERROR",
        detail: dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail or {}
        super().__init__(message)


# ——— 具体异常 ———


class NotFoundError(AppException):
    """资源未找到"""

    def __init__(self, message: str = "资源未找到", error_code: str = "NOT_FOUND"):
        super().__init__(message, status.HTTP_404_NOT_FOUND, error_code)


class UnauthorizedError(AppException):
    """未认证"""

    def __init__(self, message: str = "未登录或令牌已过期", error_code: str = "UNAUTHORIZED"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED, error_code)


class ForbiddenError(AppException):
    """无权限"""

    def __init__(self, message: str = "无权限访问", error_code: str = "FORBIDDEN"):
        super().__init__(message, status.HTTP_403_FORBIDDEN, error_code)


class BadRequestError(AppException):
    """请求参数错误"""

    def __init__(self, message: str = "请求参数错误", error_code: str = "BAD_REQUEST"):
        super().__init__(message, status.HTTP_400_BAD_REQUEST, error_code)


class ConflictError(AppException):
    """资源冲突（如重复注册）"""

    def __init__(self, message: str = "资源已存在", error_code: str = "CONFLICT"):
        super().__init__(message, status.HTTP_409_CONFLICT, error_code)


class PlanningError(AppException):
    """行程规划失败"""

    def __init__(self, message: str = "行程规划失败", error_code: str = "PLANNING_ERROR"):
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR, error_code)


class ExternalAPIError(AppException):
    """外部 API 调用失败"""

    def __init__(self, message: str = "外部服务暂时不可用", error_code: str = "EXTERNAL_API_ERROR"):
        super().__init__(message, status.HTTP_502_BAD_GATEWAY, error_code)


# ——— FastAPI 异常处理器 ———


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "detail": exc.detail if exc.detail else None,
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底处理未预期的异常"""
    import logging

    logger = logging.getLogger("app")
    logger.exception("未预期的错误: %s", exc)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": "服务器内部错误",
        },
    )
