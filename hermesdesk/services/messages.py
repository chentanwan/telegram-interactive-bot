"""Message-id mapping between the user chat and the admin topic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from hermesdesk.db.models import MessageMap


def save_map(
    session: Session,
    *,
    user_id: int,
    user_chat_message_id: int,
    group_chat_message_id: int,
) -> MessageMap:
    record = MessageMap(
        user_id=user_id,
        user_chat_message_id=user_chat_message_id,
        group_chat_message_id=group_chat_message_id,
    )
    session.add(record)
    session.flush()
    return record


def group_id_for_user_message(
    session: Session, user_chat_message_id: int, user_id: int | None = None
) -> int | None:
    query = session.query(MessageMap).filter(
        MessageMap.user_chat_message_id == user_chat_message_id
    )
    if user_id is not None:
        query = query.filter(MessageMap.user_id == user_id)
    record = query.first()
    return record.group_chat_message_id if record else None


def user_id_for_group_message(session: Session, group_chat_message_id: int) -> int | None:
    record = (
        session.query(MessageMap)
        .filter(MessageMap.group_chat_message_id == group_chat_message_id)
        .first()
    )
    return record.user_chat_message_id if record else None


def list_user_chat_message_ids(session: Session, user_id: int) -> list[int]:
    rows = session.query(MessageMap).filter(MessageMap.user_id == user_id).all()
    return [row.user_chat_message_id for row in rows]


def delete_maps_for_user(session: Session, user_id: int) -> int:
    deleted = (
        session.query(MessageMap)
        .filter(MessageMap.user_id == user_id)
        .delete(synchronize_session=False)
    )
    session.flush()
    return deleted
