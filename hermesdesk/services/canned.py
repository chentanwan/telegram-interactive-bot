"""Staff canned replies."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from hermesdesk.db.models import CannedReply

SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")


def valid_slug(slug: str) -> bool:
    return bool(SLUG_RE.match(slug or ""))


def get_reply(session: Session, slug: str) -> CannedReply | None:
    return session.query(CannedReply).filter(CannedReply.slug == slug).first()


def list_replies(session: Session) -> list[CannedReply]:
    return session.query(CannedReply).order_by(CannedReply.slug.asc()).all()


def upsert_reply(session: Session, slug: str, body: str, created_by: int | None) -> CannedReply:
    record = get_reply(session, slug)
    if record is None:
        record = CannedReply(slug=slug, body=body, created_by=created_by)
        session.add(record)
    else:
        record.body = body
        if created_by is not None:
            record.created_by = created_by
    session.flush()
    return record


def delete_reply(session: Session, slug: str) -> bool:
    record = get_reply(session, slug)
    if record is None:
        return False
    session.delete(record)
    session.flush()
    return True
