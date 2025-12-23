from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone
import enum

Base = declarative_base()


class TaskStatus(enum.Enum):
    CREATED = "created"
    SCHEDULED = "scheduled"
    SENT = "sent"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    timezone = Column(String, nullable=True)
    google_calendar_token = Column(Text, nullable=True)  # JSON with OAuth tokens

    tasks = relationship("Task", back_populates="user")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    description = Column(String)
    due_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(
        Enum(TaskStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=TaskStatus.CREATED,
    )
    message_id = Column(BigInteger, nullable=True)
    chat_id = Column(BigInteger, nullable=True)
    google_calendar_event_id = Column(String, nullable=True)  # Google Calendar event ID

    user = relationship("User", back_populates="tasks")
