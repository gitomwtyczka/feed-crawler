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
    Float,
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
    language = Column(String(5), nullable=True, default=None, doc="ISO language code: pl, en, de, fr, es, it, pt")
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

LANGUAGES = {
    "pl": {"label": "Polski", "flag": "🇵🇱", "google_hl": "pl", "google_gl": "PL", "google_ceid": "PL:pl"},
    "en": {"label": "English", "flag": "🇬🇧", "google_hl": "en", "google_gl": "US", "google_ceid": "US:en"},
    "de": {"label": "Deutsch", "flag": "🇩🇪", "google_hl": "de", "google_gl": "DE", "google_ceid": "DE:de"},
    "fr": {"label": "Français", "flag": "🇫🇷", "google_hl": "fr", "google_gl": "FR", "google_ceid": "FR:fr"},
    "es": {"label": "Español", "flag": "🇪🇸", "google_hl": "es", "google_gl": "ES", "google_ceid": "ES:es"},
    "it": {"label": "Italiano", "flag": "🇮🇹", "google_hl": "it", "google_gl": "IT", "google_ceid": "IT:it"},
    "pt": {"label": "Português", "flag": "🇵🇹", "google_hl": "pt-PT", "google_gl": "PT", "google_ceid": "PT:pt-150"},
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

    # AI enrichment (via AI Router — Bielik + Gemini)
    ai_category = Column(String(100), nullable=True, doc="AI-classified category: polityka, sport, tech...")
    ai_keywords = Column(Text, nullable=True, doc="Comma-separated AI-extracted keywords")
    ai_sentiment = Column(String(20), nullable=True, doc="positive, negative, neutral")
    ai_summary = Column(Text, nullable=True, doc="AI-generated summary (Gemini)")
    ai_processed = Column(Boolean, nullable=False, default=False, doc="True if AI enrichment was done")

    # Reprint detection
    reprint_type = Column(String(20), nullable=True, doc="original, reprint, modified_reprint")
    original_article_id = Column(Integer, ForeignKey("articles.id"), nullable=True, doc="Link to earliest matching article")
    similarity_score = Column(Float, nullable=True, doc="0.0-1.0 similarity to closest match")

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


class BroadcastStation(Base):
    """TV/Radio station for stream monitoring."""

    __tablename__ = "broadcast_stations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, doc="Station name, e.g. 'TVP Info'")
    station_type = Column(String(10), nullable=False, doc="tv | radio")
    stream_url = Column(String(2048), nullable=False, doc="HLS/HTTP stream URL")
    language = Column(String(5), nullable=False, default="pl")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    transcripts = relationship("Transcript", back_populates="station", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<BroadcastStation(id={self.id}, name='{self.name}', type={self.station_type})>"


class Transcript(Base):
    """Transcribed audio chunk from a TV/Radio broadcast."""

    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("broadcast_stations.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False, doc="Transcribed text of audio chunk")
    chunk_start = Column(DateTime, nullable=False, doc="Start time of audio chunk")
    chunk_end = Column(DateTime, nullable=False, doc="End time of audio chunk")
    keywords_found = Column(Text, nullable=True, doc="Comma-separated matched keywords")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    station = relationship("BroadcastStation", back_populates="transcripts")

    def __repr__(self) -> str:
        return f"<Transcript(station_id={self.station_id}, start={self.chunk_start}, keywords={self.keywords_found})>"


class Journalist(Base):
    """Journalist profile — opt-in registration (RODO compliant).
    
    Journalists get free Professional access in exchange for creating
    a public profile that PR agencies can search.
    """

    __tablename__ = "journalists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, doc="Full name")
    email = Column(String(255), nullable=False, unique=True, index=True)
    media_outlet = Column(String(255), nullable=True, doc="Current media outlet/redakcja")
    beat = Column(String(255), nullable=True, doc="Speciality/beat: polityka, ekonomia, tech...")
    bio = Column(Text, nullable=True, doc="Short bio / description")
    region = Column(String(100), nullable=True, doc="Region: Warszawa, Kraków, etc.")
    is_verified = Column(Boolean, nullable=False, default=False, doc="Verified via editorial email")
    rodo_consent = Column(Boolean, nullable=False, default=False, doc="Explicit RODO consent")
    rodo_consent_date = Column(DateTime, nullable=True, doc="When consent was given")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Journalist(id={self.id}, name='{self.name}', outlet='{self.media_outlet}')>"


class Project(Base):
    """Brand monitoring project — tracks a brand/topic across all sources."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, doc="Project name, e.g. 'Strabag'")
    slug = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    client_id = Column(Integer, ForeignKey("client_accounts.id"), nullable=True)

    # Relationships
    keywords = relationship("ProjectKeyword", back_populates="project", cascade="all, delete-orphan")
    client = relationship("ClientAccount", back_populates="projects")

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}', slug='{self.slug}')>"


class ProjectKeyword(Base):
    """Keyword to match articles against a project."""

    __tablename__ = "project_keywords"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    keyword = Column(String(255), nullable=False, doc="Keyword to search for (case-insensitive)")
    match_type = Column(String(20), nullable=False, default="contains", doc="contains | exact_word | regex")

    # Relationships
    project = relationship("Project", back_populates="keywords")

    def __repr__(self) -> str:
        return f"<ProjectKeyword(id={self.id}, keyword='{self.keyword}', type='{self.match_type}')>"


class ClientAccount(Base):
    """Client account for media monitoring panel."""

    __tablename__ = "client_accounts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    tier = Column(String(20), nullable=False, default="basic")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relacja do projektów
    projects = relationship("Project", back_populates="client")

    def __repr__(self) -> str:
        return f"<ClientAccount(id={self.id}, username='{self.username}', company='{self.company_name}')>"
