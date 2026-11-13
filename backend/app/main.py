from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import admin, ai_access, auth, collections, documents, invites, limits, members, tokens
from app.storage import ensure_bucket

app = FastAPI()


@app.on_event("startup")
def on_startup() -> None:
    ensure_bucket()

# Added before CORSMiddleware so CORS ends up as the outermost layer
# (Starlette wraps middleware in reverse add-order) and handles preflight
# requests before they ever reach session/auth logic.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    same_site="lax",
    https_only=settings.SESSION_HTTPS_ONLY,
    max_age=settings.SESSION_MAX_AGE_HOURS * 3600,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(collections.router)
app.include_router(documents.router)
app.include_router(members.router)
app.include_router(ai_access.router)
app.include_router(admin.router)
app.include_router(invites.router)
app.include_router(tokens.router)
app.include_router(limits.router)


@app.get("/")
async def read_root():
    return {"status": "ok"}
