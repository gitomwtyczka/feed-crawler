"""
Database connection and session management.

Supports SQLite (dev) and PostgreSQL (production).
Pattern matches SaaS backend (crimson-void/backend/database.py).
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./feed_crawler.db")

# SQLite needs check_same_thread=False for multi-threaded access
connect_args = {}
extra_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    # In-memory SQLite needs StaticPool to share DB across connections
    if DATABASE_URL == "sqlite://" or DATABASE_URL == "sqlite:///:memory:":
        extra_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False, **extra_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all models."""


def get_db():
    """Yield a DB session, ensuring cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Safe to call multiple times."""
    Base.metadata.create_all(bind=engine)
