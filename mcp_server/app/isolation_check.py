"""Live proof that Qdrant itself keeps matters apart.

Run against the real Qdrant inside the stack:

    docker compose exec -T mcp_server python -m app.isolation_check

Creates two throwaway matter collections, then checks that a token minted for
matter A can read A but not B, cannot write or delete, and that missing, wrong,
expired and forged credentials are all refused. Cleans up after itself and
exits non-zero on any failure, so it can gate a deployment.
"""

import sys
import uuid

import httpx

from app.config import settings
from app.qdrant_access import mint_read_token

URL = settings.QDRANT_URL
KEY = settings.QDRANT_API_KEY


def status(method: str, path: str, token: str | None = None, **kwargs) -> int:
    headers = {"api-key": token} if token else {}
    return httpx.request(method, URL + path, headers=headers, timeout=15, **kwargs).status_code


def main() -> int:
    suffix = uuid.uuid4().hex[:8]
    a, b = f"matter_isolationcheck_a_{suffix}", f"matter_isolationcheck_b_{suffix}"
    admin = {"api-key": KEY}
    vectors = {"vectors": {"dense": {"size": 4, "distance": "Cosine"}}}
    for name in (a, b):
        httpx.put(f"{URL}/collections/{name}", json=vectors, headers=admin, timeout=15).raise_for_status()

    failures: list[str] = []

    def expect(label: str, got: int, want) -> None:
        ok = got in want if isinstance(want, tuple) else got == want
        print(f"  {'ok  ' if ok else 'FAIL'} {label}: HTTP {got}")
        if not ok:
            failures.append(label)

    try:
        scroll = {"limit": 1}
        token_a = mint_read_token([a], KEY, 60)
        expect("token for A reads A", status("POST", f"/collections/{a}/points/scroll", token_a, json=scroll), 200)
        expect("token for A cannot read B", status("POST", f"/collections/{b}/points/scroll", token_a, json=scroll), 403)
        expect("token for A cannot write A", status("PUT", f"/collections/{a}/points", token_a, json={"points": []}), 403)
        expect("token for A cannot delete A", status("DELETE", f"/collections/{a}", token_a), 403)
        expect("token for A cannot create collections", status("PUT", f"/collections/{a}_x", token_a, json=vectors), 403)
        expect("no credentials are refused", status("POST", f"/collections/{a}/points/scroll", None, json=scroll), 401)
        expect("a wrong key is refused", status("POST", f"/collections/{a}/points/scroll", "wrong", json=scroll), 401)
        expired = mint_read_token([a], KEY, 60, now=1000)
        expect("an expired token is refused", status("POST", f"/collections/{a}/points/scroll", expired, json=scroll), (401, 403))
        forged = mint_read_token([a], "not-the-real-secret-not-the-real-secret", 60)
        expect("a token signed with another secret is refused", status("POST", f"/collections/{a}/points/scroll", forged, json=scroll), (401, 403))
        nobody = mint_read_token([], KEY, 60)
        expect("a token for no matters reads nothing", status("POST", f"/collections/{a}/points/scroll", nobody, json=scroll), 403)
    finally:
        for name in (a, b):
            httpx.delete(f"{URL}/collections/{name}", headers=admin, timeout=15)

    print("ISOLATION OK" if not failures else f"ISOLATION FAILED: {', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
