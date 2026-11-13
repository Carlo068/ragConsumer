"""Which matters a person's AI may reach. The single rule behind every tool
call, kept free of model and Qdrant imports so it can be tested directly."""

from sqlalchemy import text
from sqlalchemy.engine import Engine


def matter_collection_name(matter_id: str) -> str:
    # One Qdrant collection per matter. Must match the backend and the worker.
    return f"matter_{matter_id}"


def get_allowed_matters(engine: Engine, user_id: str) -> dict[str, str]:
    """The matters this person's AI may search right now: {matter id: name}.

    Read fresh on every call, never cached or taken from a tool argument. A
    matter counts only if the person both chose it for their AI *and* is still
    a member of it. The second condition is the security one: removing someone
    from a matter cuts their AI off on its very next call, whatever they had
    selected before.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT c.id, c.name FROM ai_matter_selections s "
                "JOIN collection_members m "
                "  ON m.collection_id = s.collection_id AND m.user_id = s.user_id "
                "JOIN collections c ON c.id = s.collection_id "
                "WHERE s.user_id = :user_id ORDER BY c.name"
            ),
            {"user_id": user_id},
        ).all()
    return {str(row[0]): row[1] for row in rows}
