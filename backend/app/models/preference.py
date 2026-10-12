"""偏好 & 用户画像模型"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    default_departure_city: Mapped[str | None] = mapped_column(String(100))
    preferred_hotel_star: Mapped[int] = mapped_column(Integer, default=4)
    preferred_flight_class: Mapped[str] = mapped_column(String(20), default="economy")
    pace: Mapped[str] = mapped_column(String(20), default="moderate")
    interests: Mapped[list | None] = mapped_column(sa.JSON, default=list)
    dietary: Mapped[list | None] = mapped_column(sa.JSON, default=list)
    budget_default_currency: Mapped[str] = mapped_column(String(3), default="CNY")
    default_travelers: Mapped[list | None] = mapped_column(sa.JSON, default=lambda: [{"age": 30, "type": "adult"}])
    is_first_time: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="preference")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    label: Mapped[str | None] = mapped_column(String(50))
    traits: Mapped[list | None] = mapped_column(sa.JSON, default=list)
    budget_flexibility: Mapped[str | None] = mapped_column(String(20))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="profile")
