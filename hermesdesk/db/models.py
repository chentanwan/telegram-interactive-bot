from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from hermesdesk.db.session import Base


class MediaGroupMessage(Base):
    __tablename__ = "media_group_message"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, index=True)
    message_id = Column(Integer)
    media_group_id = Column(String(64), index=True)
    is_header = Column(Boolean, default=False)
    caption_html = Column(String(1024 * 64))


class FormnStatus(Base):
    __tablename__ = "formn_status"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer)
    message_thread_id = Column(Integer, index=True)
    status = Column(String(64), default="opened")


class MessageMap(Base):
    __tablename__ = "message_map"

    id = Column(Integer, primary_key=True, index=True)
    user_chat_message_id = Column(Integer, index=True)
    group_chat_message_id = Column(Integer, index=True)
    user_id = Column(Integer, index=True)


class User(Base):
    __tablename__ = "user"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_user_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True, nullable=False)
    first_name = Column(String(64))
    last_name = Column(String(64))
    username = Column(String(64))
    is_premium = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)
    note = Column(String(1024 * 4))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    message_thread_id = Column(Integer, default=0)
