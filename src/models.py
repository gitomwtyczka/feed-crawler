"""
SQLAlchemy models for Feed Crawler.

Tables:
- Feed: RSS/API source definition
- Department: Thematic department (e.g. science, defence)
- FeedDepartment: M2M feed <-> department
- Article: Fetched article from a feed
- ArticleDepartment: M2M article <-> department
- FetchLog: Per-feed fetch execution log
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class Feed(Base):
    """RSS/API source definition."""

    __tablename__ = "feeds"

    # Source tier constants
    TIER_SCIENTIFIC = 1      # 🔬 PubMed, Nature, Science, Lancet, arXiv
    TIER_INDUSTRY = 2        # 🎓 STAT News, MedPage, BIS, IRENA, think tanks
    TIER_QUALITY_NEWS = 3    # 📰 Reuters, BBC, Guardian, PAP, ISBNews
    TIER_PORTAL = 4          # 📱 WP, Onet, TVN24, Interia, general portals
    TIER_UGC = 5             # 💬 Reddit, X/Twitter, blogs, forums

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(2048), nullable=True, default="", doc="Website URL")
    rss_url = Column(String(2048), nullable=True, default="", doc="RSS/Atom feed URL")
    feed_type = Column(String(20), nullable=False, default="rss", doc="rss | atom | api")
    source_tier = Column(Integer, nullable=False, default=4, doc="Source tier: 1=Scientific 2=Industry 3=QualityNews 4=Portal 5=UGC")
    fetch_interval = Column(Integer, nullable=False, default=30, doc="Fetch interval in minutes")
    is_active = Column(Boolean, nullable=False, default=True)
    last_fetched = Column(DateTime, nullable=True)
    consecutive_errors = Column(Integer, nullable=False, default=0, doc="Consecutive fetch failures (reset on success)")
    backoff_until = Column(DateTime, nullable=True, doc="Skip fetching until this time (exponential backoff)")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    departments = relationship("Department", secondary="feed_departments", back_populates="feeds")
    articles = relationship("Article", back_populates="feed", cascade="all, delete-orphan")
    fetch_logs = relationship("FetchLog", back_populates="feed", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Feed(id={self.id}, name='{self.name}', tier={self.source_tier}, active={self.is_active})>"


# Tier display helpers
SOURCE_TIERS = {
    1: {"label": "Naukowe", "emoji": "🔬", "color": "#a78bfa"},
    2: {"label": "Branżowe", "emoji": "🎓", "color": "#60a5fa"},
    3: {"label": "Quality News", "emoji": "📰", "color": "#34d399"},
    4: {"label": "Portal", "emoji": "📱", "color": "#fbbf24"},
    5: {"label": "UGC", "emoji": "💬", "color": "#f87171"},
}


class Department(Base):
    """Thematic department (maps to OPML categories)."""

    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, doc="Display name, e.g. 'SCIENCE & HIGH-TECH'")
    slug = Column(String(100), nullable=False, unique=True, doc="URL-safe slug, e.g. 'science-hightech'")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    feeds = relationship("Feed", secondary="feed_departments", back_populates="departments")
    articles = relationship("Article", secondary="article_departments", back_populates="departments")

    def __repr__(self) -> str:
        return f"<Department(id={self.id}, slug='{self.slug}')>"


class FeedDepartment(Base):
    """Many-to-many: Feed <-> Department."""

    __tablename__ = "feed_departments"

    feed_id = Column(Integer, ForeignKey("feeds.id", ondelete="CASCADE"), primary_key=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True)


class Article(Base):
    """Fetched article from a feed."""

    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    feed_id = Column(Integer, ForeignKey("feeds.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(1024), nullable=False)
    url = Column(String(2048), nullable=False)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True, doc="Full content if available from feed")
    author = Column(String(255), nullable=True)
    published_at = Column(DateTime, nullable=True, doc="Publication date from feed")
    hash = Column(String(64), nullable=False, unique=True, index=True, doc="SHA256 dedup hash")
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    sent_to_saas = Column(Boolean, nullable=False, default=False)
    sent_at = Column(DateTime, nullable=True)

    # Relationships
    feed = relationship("Feed", back_populates="articles")
    departments = relationship("Department", secondary="article_departments", back_populates="articles")

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title='{self.title[:50]}...')>"


class ArticleDepartment(Base):
    """Many-to-many: Article <-> Department."""

    __tablename__ = "article_departments"

    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True)


class FetchLog(Base):
    """Per-feed fetch execution log for monitoring and debugging."""

    __tablename__ = "fetch_logs"

    id = Column(Integer, primary_key=True, index=True)
    feed_id = Column(Integer, ForeignKey("feeds.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="running", doc="running | success | error")
    articles_found = Column(Integer, nullable=False, default=0)
    articles_new = Column(Integer, nullable=False, default=0, doc="After dedup")
    error_message = Column(Text, nullable=True)

    # Relationships
    feed = relationship("Feed", back_populates="fetch_logs")

    __table_args__ = (
        UniqueConstraint("feed_id", "started_at", name="uq_fetch_log_feed_time"),
    )

    def __repr__(self) -> str:
        return f"<FetchLog(feed_id={self.feed_id}, status='{self.status}', new={self.articles_new})>"
