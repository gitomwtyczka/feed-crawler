"""
Authentication module for Feed Crawler Admin Panel.

JWT-based auth with password hashing.
Admin users stored in DB with bcrypt hashed passwords.

Usage:
    Set JWT_SECRET in .env (REQUIRED in production).
    Default admin: admin / admin (auto-created on first run).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import Boolean, Column, DateTime, Integer, String

from .database import Base

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

load_dotenv()

logger = logging.getLogger(__name__)

# ── Config ──
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ── Admin User Model ──


class AdminUser(Base):
    """Admin panel user."""

    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<AdminUser(username='{self.username}')>"


# ── Password helpers ──


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ──


def create_access_token(username: str) -> str:
    """Create a JWT access token."""
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {
        "sub": username,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Decode a JWT token. Returns username or None if invalid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


# ── DB helpers ──


def get_admin_user(db: Session, username: str) -> AdminUser | None:
    """Get admin user by username."""
    return db.query(AdminUser).filter(AdminUser.username == username).first()


def authenticate_user(db: Session, username: str, password: str) -> AdminUser | None:
    """Authenticate user. Returns user if valid, None otherwise."""
    user = get_admin_user(db, username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    return user


def ensure_default_admin(db: Session) -> None:
    """Create default admin user if none exist."""
    count = db.query(AdminUser).count()
    if count == 0:
        admin = AdminUser(
            username="admin",
            password_hash=hash_password("admin"),
        )
        db.add(admin)
        db.commit()
        logger.info("Created default admin user (admin/admin) — CHANGE PASSWORD IN PRODUCTION!")
