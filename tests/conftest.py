"""
Shared fixtures for feed-crawler tests.

Pattern matches SaaS backend (crimson-void/backend/tests/conftest.py):
- In-memory SQLite test DB
- Session-scoped fixtures
- Automatic cleanup
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Override DATABASE_URL before any src imports
os.environ["DATABASE_URL"] = "sqlite://"  # in-memory

from src import models as _models  # noqa: E402, F401  — ensure all tables registered
from src.database import Base  # noqa: E402

# ── In-memory SQLite for tests ──
test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables before tests, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    """Yield a fresh DB session per test, with rollback."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ── Sample data fixtures ──

SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>A test feed</description>
    <item>
      <title>Discovery of New Planet</title>
      <link>https://example.com/articles/new-planet</link>
      <description>Scientists have discovered a new exoplanet.</description>
      <pubDate>Mon, 10 Mar 2026 12:00:00 GMT</pubDate>
      <author>Dr. Smith</author>
    </item>
    <item>
      <title>Quantum Computing Breakthrough</title>
      <link>https://example.com/articles/quantum</link>
      <description>Major advance in quantum error correction.</description>
      <pubDate>Mon, 10 Mar 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Climate Report 2026</title>
      <link>https://example.com/articles/climate-2026</link>
      <description>New IPCC report highlights urgent action needed.</description>
      <pubDate>Sun, 09 Mar 2026 15:00:00 GMT</pubDate>
      <author>IPCC Team</author>
    </item>
  </channel>
</rss>"""

SAMPLE_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Test Feed</title>
  <link href="https://atom-example.com"/>
  <entry>
    <title>Atom Entry One</title>
    <link href="https://atom-example.com/entry-1"/>
    <summary>First atom entry summary.</summary>
    <updated>2026-03-10T12:00:00Z</updated>
    <author><name>Author A</name></author>
  </entry>
</feed>"""

EMPTY_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Empty Feed</title>
    <link>https://empty.example.com</link>
    <description>No items here</description>
  </channel>
</rss>"""

MALFORMED_XML = """<?xml version="1.0"?>
<rss><channel><title>Broken"""


SAMPLE_OPML = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Test OPML</title></head>
  <body>
    <outline title="SCIENCE" text="SCIENCE">
      <outline type="rss" text="Nature" title="Nature"
               xmlUrl="http://feeds.nature.com/rss" htmlUrl="https://nature.com"/>
      <outline type="rss" text="NASA" title="NASA"
               xmlUrl="https://nasa.gov/rss" htmlUrl="https://nasa.gov"/>
    </outline>
    <outline title="HEALTH" text="HEALTH">
      <outline type="rss" text="WHO" title="WHO"
               xmlUrl="https://who.int/rss" htmlUrl="https://who.int"/>
    </outline>
  </body>
</opml>"""


@pytest.fixture
def sample_rss():
    return SAMPLE_RSS_XML


@pytest.fixture
def sample_atom():
    return SAMPLE_ATOM_XML


@pytest.fixture
def empty_rss():
    return EMPTY_RSS_XML


@pytest.fixture
def malformed_xml():
    return MALFORMED_XML


@pytest.fixture
def sample_opml(tmp_path):
    """Write sample OPML to a temp file and return path."""
    opml_file = tmp_path / "test.opml"
    opml_file.write_text(SAMPLE_OPML, encoding="utf-8")
    return str(opml_file)
