"""Identifiers the AI passes in (chunk ids, document ids) are UUIDs. Anything else
is "no such thing", answered like a missing id, instead of being handed to Qdrant
and returning its error message to the model."""

import uuid


def is_valid_id(value: str) -> bool:
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True
