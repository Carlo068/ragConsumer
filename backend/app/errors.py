"""Errors the web app shows to people.

An ApiError is an HTTPException that also carries a stable `code` (and any
`params` the message needs, such as a limit). The English `detail` stays for
logs and API users; the web app ignores it and shows its own translation of
the code, so raw English never reaches a Spanish-speaking lawyer's screen.

Every code used must be listed in error_codes.json, which the frontend's
Spanish and English message files are checked against.
"""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, *, headers: dict | None = None, **params):
        super().__init__(status_code, message, headers=headers)
        self.code = code
        self.params = params


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code, "params": exc.params},
        headers=getattr(exc, "headers", None),
    )
