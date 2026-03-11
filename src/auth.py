"""
Authentication module for Feed Crawler Admin Panel.

JWT-based auth with password hashing.
Admin users stored in DB with bcrypt hashed passwords.

Roles:
    admin   — Full access + user management
    editor  — Dashboard, feeds, discovery, monitoring, settings
    viewer  — Read-only: dashboard, reader, search

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

ROLES = ("admin", "editor", "viewer")
ROLE_HIERARCHY = {"admin": 3, "editor": 2, "viewer": 1}

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# ── Admin User Model ──


class AdminUser(Base):
    """Admin panel user."""

    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    role = Column(String(20), nullable=False, default="viewer")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<AdminUser(username='{self.username}', role='{self.role}')>"


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
            role="admin",
        )
        db.add(admin)
        db.commit()
        logger.info("Created default admin user (admin/admin) — CHANGE PASSWORD IN PRODUCTION!")
    else:
        # Ensure existing admin user has role set
        admin = db.query(AdminUser).filter(AdminUser.username == "admin").first()
        if admin and not admin.role:
            admin.role = "admin"
            db.commit()


# ── Permission helpers ──


def has_permission(user_role: str, required_role: str) -> bool:
    """Check if user_role has at least required_role level.

    Hierarchy: admin (3) > editor (2) > viewer (1)
    """
    return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(required_role, 0)


# ── User CRUD ──


def list_users(db: Session) -> list[AdminUser]:
    """List all admin users."""
    return db.query(AdminUser).order_by(AdminUser.created_at).all()


def create_user(
    db: Session,
    username: str,
    password: str,
    role: str = "viewer",
    email: str = "",
) -> AdminUser:
    """Create a new admin user."""
    if role not in ROLES:
        msg = f"Invalid role: {role}"
        raise ValueError(msg)
    user = AdminUser(
        username=username,
        password_hash=hash_password(password),
        role=role,
        email=email or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Created user: %s (role=%s)", username, role)
    return user


def update_user(
    db: Session,
    user_id: int,
    *,
    email: str | None = None,
    role: str | None = None,
    password: str | None = None,
    is_active: bool | None = None,
) -> AdminUser | None:
    """Update an existing user. Only provided fields are changed."""
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        return None
    if email is not None:
        user.email = email or None
    if role is not None:
        if role not in ROLES:
            msg = f"Invalid role: {role}"
            raise ValueError(msg)
        user.role = role
    if password:
        user.password_hash = hash_password(password)
    if is_active is not None:
        user.is_active = is_active
    db.commit()
    db.refresh(user)
    logger.info("Updated user: %s (id=%d)", user.username, user.id)
    return user


def delete_user(db: Session, user_id: int) -> bool:
    """Delete a user by ID. Cannot delete last admin."""
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        return False
    # Prevent deleting the last admin
    if user.role == "admin":
        admin_count = db.query(AdminUser).filter(
            AdminUser.role == "admin",
            AdminUser.id != user_id,
        ).count()
        if admin_count == 0:
            logger.warning("Cannot delete last admin user: %s", user.username)
            return False
    db.delete(user)
    db.commit()
    logger.info("Deleted user: %s (id=%d)", user.username, user_id)
    return True
