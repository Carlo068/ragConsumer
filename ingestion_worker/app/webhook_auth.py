"""Who may poke the worker through /webhook.

The call only wakes the worker (it also polls on its own), so the stakes are low,
but the port is internal and the caller is known: the storage service, which sends a
shared token with every notification. Anything else is refused. With no token
configured, everything is refused (fail closed)."""

import hmac


def webhook_authorized(header: str | None, token: str) -> bool:
    if not token or not header:
        return False
    presented = header.strip()
    if presented.lower().startswith("bearer "):
        presented = presented[7:].strip()
    return hmac.compare_digest(presented.encode(), token.encode())
