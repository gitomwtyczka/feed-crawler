"""Tests for FastAPI web application (admin + reader + API).

web.py uses db_module.SessionLocal() which is the production SessionLocal.
However, conftest.py already overrides DATABASE_URL to 'sqlite://' before
any src imports. So database.SessionLocal is already in-memory.
We just need to ensure tables are created on that engine.
"""

from fastapi.testclient import TestClient

from src import models as _models  # noqa: F401
from src.database import Base, engine
from src.web import app

# Create tables on the engine that database.SessionLocal is bound to
Base.metadata.create_all(bind=engine)

client = TestClient(app)


# ── API Tests ──


class TestApiStats:
    def test_stats_endpoint(self):
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_feeds" in data
        assert "total_articles" in data
        assert "active_feeds" in data
        assert "articles_24h" in data
        assert "departments" in data

    def test_stats_values_are_integers(self):
        response = client.get("/api/stats")
        data = response.json()
        for key in ["total_feeds", "total_articles", "active_feeds", "articles_24h", "departments"]:
            assert isinstance(data[key], int)

    def test_stats_zero_on_empty_db(self):
        response = client.get("/api/stats")
        data = response.json()
        assert data["total_feeds"] == 0
        assert data["total_articles"] == 0


class TestApiArticles:
    def test_articles_endpoint(self):
        response = client.get("/api/articles")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "articles" in data
        assert isinstance(data["articles"], list)

    def test_articles_pagination(self):
        response = client.get("/api/articles?page=1&per_page=5")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["per_page"] == 5

    def test_articles_max_per_page(self):
        response = client.get("/api/articles?per_page=500")
        assert response.status_code == 422


class TestApiFeeds:
    def test_feeds_endpoint(self):
        response = client.get("/api/feeds")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "feeds" in data
        assert data["total"] == 0


# ── Reader Tests ──


class TestReaderRoutes:
    def test_home_page(self):
        response = client.get("/")
        assert response.status_code == 200
        assert "Latest News" in response.text or "Feed Crawler" in response.text

    def test_search_page(self):
        response = client.get("/search")
        assert response.status_code == 200
        assert "Search" in response.text

    def test_search_with_query(self):
        response = client.get("/search?q=test")
        assert response.status_code == 200

    def test_feed_not_found(self):
        response = client.get("/feed/99999")
        assert response.status_code == 404

    def test_article_not_found(self):
        response = client.get("/article/99999")
        assert response.status_code == 404

    def test_department_not_found(self):
        response = client.get("/department/nonexistent-dept")
        assert response.status_code == 404


# ── Admin Tests ──


class TestAdminRoutes:
    def test_admin_dashboard(self):
        response = client.get("/admin")
        assert response.status_code == 200
        assert "Dashboard" in response.text

    def test_admin_feeds(self):
        response = client.get("/admin/feeds")
        assert response.status_code == 200
        assert "Feed Management" in response.text

    def test_toggle_nonexistent_feed(self):
        response = client.post("/admin/feeds/99999/toggle", follow_redirects=False)
        assert response.status_code == 303
