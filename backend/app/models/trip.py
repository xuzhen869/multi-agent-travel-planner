"""行程模型"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import String, DateTime, ForeignKey, func, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    mode: Mapped[str] = mapped_column(String(20), default="recommend")
    request_params: Mapped[dict] = mapped_column(sa.JSON, default=dict)
    recommendations: Mapped[dict | None] = mapped_column(sa.JSON)
    selected_plan_id: Mapped[str | None] = mapped_column(String(20))
    plan_data: Mapped[dict | None] = mapped_column(sa.JSON)
    user_profile: Mapped[dict | None] = mapped_column(sa.JSON)
    budget_total: Mapped[float | None] = mapped_column(Numeric(12, 2))
    budget_currency: Mapped[str | None] = mapped_column(String(3))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="trips")
