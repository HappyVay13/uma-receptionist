from sqlalchemy import String, DateTime, Text, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone

from .database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # client_id
    business_name: Mapped[str] = mapped_column(String(200), default="Repliq")
    status: Mapped[str] = mapped_column(String(32), default="trial")  # trial/active/inactive
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id"), index=True)
    user_key: Mapped[str] = mapped_column(String(96), index=True)  # normalized phone
    lang_lock: Mapped[str] = mapped_column(String(8), default="lv")
    state: Mapped[str] = mapped_column(String(32), default="NEW")

    service: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    datetime_iso: Mapped[str | None] = mapped_column(String(64), nullable=True)
    time_text: Mapped[str | None] = mapped_column(String(64), nullable=True)

    pending_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "user_key", name="uq_conv_tenant_user"),)

class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.id"), index=True)
    user_key: Mapped[str] = mapped_column(String(96), index=True)
    start_iso: Mapped[str] = mapped_column(String(64))
    service: Mapped[str] = mapped_column(String(200))
    gcal_event_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
