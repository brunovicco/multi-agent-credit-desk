"""Shared base configuration and reusable field types for credit desk contracts."""

from datetime import datetime, timedelta
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


def _require_utc(value: datetime) -> datetime:
    """Reject naive datetimes and datetimes not expressed in UTC.

    Args:
        value: The datetime produced by Pydantic's own parsing.

    Returns:
        The same datetime, once confirmed timezone-aware and UTC.

    Raises:
        ValueError: If the datetime is naive or uses a non-UTC offset.
    """
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware and expressed in UTC")
    return value


UtcDatetime = Annotated[datetime, AfterValidator(_require_utc)]


class StrictContract(BaseModel):
    """Base model for every credit desk contract: immutable and closed to unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
