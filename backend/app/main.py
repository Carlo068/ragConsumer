from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, collections

app = FastAPI()

# Added before CORSMiddleware so CORS ends up as the outermost layer
# (Starlette wraps middleware in reverse add-order) and handles preflight
# requests before they ever reach session/auth logic.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    same_site="lax",
    https_only=False,  # flip to True once served over HTTPS/Tailscale
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


@app.get("/")
async def read_root():
    return {"status": "ok"}
