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
    record = get_map_by_user_message(session, user_chat_message_id, user_id)
    return record.group_chat_message_id if record else None


def user_id_for_group_message(session: Session, group_chat_message_id: int) -> int | None:
    record = get_map_by_group_message(session, group_chat_message_id)
    return record.user_chat_message_id if record else None


def get_map_by_user_message(
    session: Session, user_chat_message_id: int, user_id: int | None = None
) -> MessageMap | None:
    query = session.query(MessageMap).filter(
        MessageMap.user_chat_message_id == user_chat_message_id
    )
    if user_id is not None:
        query = query.filter(MessageMap.user_id == user_id)
    return query.first()


def get_map_by_group_message(
    session: Session, group_chat_message_id: int
) -> MessageMap | None:
    return (
        session.query(MessageMap)
        .filter(MessageMap.group_chat_message_id == group_chat_message_id)
        .first()
    )


def delete_map(session: Session, record: MessageMap) -> None:
    session.delete(record)
    session.flush()


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
