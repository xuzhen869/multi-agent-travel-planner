from app.core.database import Base

# 导入所有模型以确保 Base.metadata 能发现它们
from app.models.user import User
from app.models.preference import UserPreference, UserProfile
from app.models.trip import Trip

__all__ = ["Base", "User", "UserPreference", "UserProfile", "Trip"]
