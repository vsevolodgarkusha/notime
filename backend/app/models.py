from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone
import enum

Base = declarative_base()

class TaskStatus(enum.Enum):
    CREATED = "created"
    SENT = "sent"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FriendshipStatus(enum.Enum):
    PENDING = "pending"      # Waiting for response
    ACCEPTED = "accepted"    # Friend request accepted
    REJECTED = "rejected"    # Friend request rejected


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    telegram_username = Column(String, nullable=True, index=True)
    timezone = Column(String)
    google_calendar_token = Column(Text, nullable=True)  # JSON with OAuth tokens
    tasks = relationship("Task", back_populates="user")

    # Friendships where this user is the requester
    sent_friend_requests = relationship(
        "Friendship",
        foreign_keys="Friendship.from_user_id",
        back_populates="from_user"
    )
    # Friendships where this user is the recipient
    received_friend_requests = relationship(
        "Friendship",
        foreign_keys="Friendship.to_user_id",
        back_populates="to_user"
    )


class Friendship(Base):
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True, index=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(FriendshipStatus), default=FriendshipStatus.PENDING)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="sent_friend_requests")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="received_friend_requests")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    description = Column(String)
    due_date = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(Enum(TaskStatus), default=TaskStatus.CREATED)
    message_id = Column(BigInteger, nullable=True)
    chat_id = Column(BigInteger, nullable=True)
    google_calendar_event_id = Column(String, nullable=True)  # Google Calendar event ID

    user = relationship("User", back_populates="tasks")
