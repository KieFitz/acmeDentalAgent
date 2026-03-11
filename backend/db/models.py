from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.database import Base


class AppointmentPin(Base):
    __tablename__ = "appointment_pins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    appointment_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    patient_name: Mapped[str] = mapped_column(String)
    patient_email: Mapped[str] = mapped_column(String)
    pin_hash: Mapped[str] = mapped_column(String)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
