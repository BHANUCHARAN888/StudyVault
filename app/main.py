from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import engine
from app.routers.auth import router as auth_router
from app.routers.documents import router as documents_router
from app.routers.subjects import router as subjects_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()

app = FastAPI(
    title=settings.app_name,
    description="Backend API for StudyVault.",
    version="0.1.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    expose_headers=["X-Total-Count"],
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://studyvault-psi.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
)


app.include_router(auth_router)
app.include_router(subjects_router)
app.include_router(documents_router)


@app.get("/", tags=["Health"])
def root():
    return {
        "message": "Welcome to StudyVault API",
        "status": "running",
    }


@app.get("/health", tags=["Health"])
def health():
    return {
        "status": "healthy",
    }


@app.get("/health/db", tags=["Health"])
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "connected",
        }

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable",
        ) from exc
