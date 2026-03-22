# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.router import router

app = FastAPI(
    title="RAG System API",
    description="Scientific Paper RAG System",
    version="1.0.0"
)

# CORS – erlaubt React Frontend auf Port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Development
        "http://localhost",        # Docker
        "http://localhost:80",     # Docker explizit
        "*"                        # Temporär für Testing
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)