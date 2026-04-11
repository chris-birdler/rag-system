from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.router import router
from backend.app.db.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    print("Database initialized")
    yield
    # Shutdown (optional)

app = FastAPI(
    title="RAG System API",
    description="Scientific Paper RAG System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS – erlaubt React Frontend auf Port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Development
        "http://localhost",        # Docker
        "http://localhost:80",     # Docker explizit
        "https://papers.mccv.at",  # Production
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)