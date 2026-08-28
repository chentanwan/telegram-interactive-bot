"""Forum topic open/close state."""

from __future__ import annotations

from sqlalchemy.orm import Session

from hermesdesk.db.models import FormnStatus, User


def get_topic_status(session: Session, message_thread_id: int) -> FormnStatus | None:
    return (
        session.query(FormnStatus)
        .filter(FormnStatus.message_thread_id == message_thread_id)
        .first()
    )


def set_topic_status(
    session: Session,
    message_thread_id: int,
    status: str,
    chat_id: int | None = None,
) -> FormnStatus:
    record = get_topic_status(session, message_thread_id)
    if record is None:
        record = FormnStatus(message_thread_id=message_thread_id, status=status)
        if chat_id is not None:
            record.chat_id = chat_id
        session.add(record)
    else:
        record.status = status
        if chat_id is not None:
            record.chat_id = chat_id
    session.flush()
    return record


def is_topic_closed(session: Session, message_thread_id: int | None) -> bool:
    if not message_thread_id:
        return False
    record = get_topic_status(session, message_thread_id)
    return bool(record and record.status == "closed")


def count_open_topics(session: Session) -> int:
    return session.query(FormnStatus).filter(FormnStatus.status == "opened").count()


def reset_user_topic(session: Session, user: User) -> None:
    thread_id = user.message_thread_id
    if thread_id:
        record = get_topic_status(session, thread_id)
        if record is not None:
            session.delete(record)
    user.message_thread_id = 0
    session.flush()
