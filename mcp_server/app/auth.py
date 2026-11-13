from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from sqlalchemy.engine import Engine

from app.tokens import find_token_owner


class PersonalTokenVerifier:
    """Accepts only personal access tokens created in the web app. The token
    decides who is asking; nothing the AI client sends can change that."""

    def __init__(self, engine: Engine):
        self._engine = engine

    async def verify_token(self, token: str) -> AccessToken | None:
        owner = find_token_owner(self._engine, token)
        if owner is None:
            return None
        return AccessToken(
            token=token,
            client_id=owner.token_id,
            scopes=[],
            subject=owner.user_id,
        )


def current_user_id() -> str:
    """The authenticated caller of the tool being run right now."""
    access = get_access_token()
    if access is None or not access.subject:
        # Unreachable while the verifier guards every request; fail closed anyway.
        raise PermissionError("Not authenticated")
    return access.subject
