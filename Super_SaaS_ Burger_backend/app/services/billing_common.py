"""Shared validation and transactional boundaries for the internal billing domain."""
from contextlib import contextmanager
from datetime import datetime, timezone
import re

from sqlalchemy.orm import Session


class BillingError(ValueError):
    """A stable internal error code; no external payload content is included."""


class BillingConflict(BillingError):
    pass


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def identifier(value: str, max_length: int = 255) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > max_length:
        raise BillingError("invalid_identifier")
    return value


def scope(provider: str, environment: str) -> None:
    identifier(provider, 50)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", provider):
        raise BillingError("invalid_provider")
    if environment not in {"sandbox", "production"}:
        raise BillingError("invalid_environment")


@contextmanager
def billing_transaction(db: Session):
    """Own a transaction on an idle Session, or a savepoint inside the caller's UoW.

    SQLite's legacy driver defers BEGIN, which otherwise lets a released SAVEPOINT
    escape an outer rollback. Explicitly start the physical transaction first.
    """
    if not db.in_transaction():
        with db.begin():
            yield
    else:
        connection = db.connection()
        if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN")
        with db.begin_nested():
            yield
