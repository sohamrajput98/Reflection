from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from app.api.routes import router
from app.core.bootstrap import get_settings

# LOAD ENV
load_dotenv()

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    summary="Campaign retrospective system for memory-backed learning loops.",
)

# ✅ ADD THIS BLOCK (CORS FIX)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "*"  # fast fix (ok for now)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ROUTES
app.include_router(router)

@app.get("/")
def home():
    return {"status": "running"}

# TEMP DEBUG (remove later)
print("DB:", os.getenv("DATABASE_URL"))
print("AGENT:", os.getenv("agent_id"))