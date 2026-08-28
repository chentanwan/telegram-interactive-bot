"""User upsert and lookup."""

from __future__ import annotations

from datetime import datetime, timezone

import telegram
from sqlalchemy.orm import Session

from hermesdesk.db.models import User


def upsert_user(session: Session, tg_user: telegram.User) -> User:
    user = session.query(User).filter(User.user_id == tg_user.id).first()
    now = datetime.now(timezone.utc)
    if user is None:
        user = User(
            user_id=tg_user.id,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            username=tg_user.username,
            is_premium=bool(tg_user.is_premium),
            last_seen_at=now,
        )
        session.add(user)
        session.flush()
        return user

    user.first_name = tg_user.first_name
    user.last_name = tg_user.last_name
    user.username = tg_user.username
    user.is_premium = bool(tg_user.is_premium)
    user.last_seen_at = now
    session.flush()
    return user


def get_user_by_id(session: Session, user_id: int) -> User | None:
    return session.query(User).filter(User.user_id == user_id).first()


def get_user_by_thread(session: Session, message_thread_id: int) -> User | None:
    return (
        session.query(User)
        .filter(User.message_thread_id == message_thread_id)
        .first()
    )


def list_users(session: Session) -> list[User]:
    return session.query(User).all()


def count_users(session: Session) -> int:
    return session.query(User).count()


def count_banned(session: Session) -> int:
    return session.query(User).filter(User.is_banned.is_(True)).count()
