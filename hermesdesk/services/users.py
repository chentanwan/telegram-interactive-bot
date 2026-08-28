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


def count_blocked(session: Session) -> int:
    return session.query(User).filter(User.is_blocked.is_(True)).count()


def list_broadcast_targets(session: Session) -> list[User]:
    return (
        session.query(User)
        .filter(User.is_banned.is_(False), User.is_blocked.is_(False))
        .all()
    )


def set_banned(session: Session, user: User, banned: bool) -> User:
    user.is_banned = banned
    session.flush()
    return user


def set_blocked(session: Session, user: User, blocked: bool) -> User:
    user.is_blocked = blocked
    session.flush()
    return user


def mark_blocked_by_ids(session: Session, user_ids: list[int]) -> int:
    if not user_ids:
        return 0
    users = session.query(User).filter(User.user_id.in_(user_ids)).all()
    for user in users:
        user.is_blocked = True
    session.flush()
    return len(users)


def set_note(session: Session, user: User, note: str | None) -> User:
    user.note = note
    session.flush()
    return user


def set_claim(
    session: Session,
    user: User,
    *,
    staff_id: int | None,
    staff_name: str | None,
) -> User:
    user.claimed_by = staff_id
    user.claimed_by_name = staff_name
    user.claimed_at = datetime.now(timezone.utc) if staff_id else None
    session.flush()
    return user


def claim_label(user: User) -> str:
    if not user.claimed_by:
        return "未认领"
    who = user.claimed_by_name or str(user.claimed_by)
    return f"{who}（{user.claimed_by}）"


def count_claimed(session: Session) -> int:
    return session.query(User).filter(User.claimed_by.isnot(None)).count()
