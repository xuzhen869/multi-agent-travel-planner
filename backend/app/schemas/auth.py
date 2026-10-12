"""认证相关 Pydantic schemas"""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """注册请求"""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    """登录请求"""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """令牌响应"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: str  # ISO 8601


class RefreshRequest(BaseModel):
    """刷新令牌请求"""

    refresh_token: str


class LogoutRequest(BaseModel):
    """登出请求"""

    refresh_token: str


class OAuthCallbackRequest(BaseModel):
    """OAuth 回调请求"""

    code: str
    redirect_uri: str | None = None
