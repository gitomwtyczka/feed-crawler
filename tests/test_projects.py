"""Tests for Project tracking models and API endpoints."""

from fastapi.testclient import TestClient

from src import database  # noqa: F401
from src.database import Base, engine
from src.models import Article, Feed, Project, ProjectKeyword
from src.web import app

# Ensure tables exist
Base.metadata.create_all(bind=engine)

client = TestClient(app)


# ── Model Tests ──


class TestProjectModels:
    def test_create_project(self, db):
        project = Project(name="Test Brand", slug="test-brand-model")
        db.add(project)
        db.flush()
        assert project.id is not None
        assert project.is_active is True

    def test_create_project_with_keywords(self, db):
        project = Project(name="KW Test", slug="kw-test-model")
        db.add(project)
        db.flush()

        kw1 = ProjectKeyword(project_id=project.id, keyword="Brand")
        kw2 = ProjectKeyword(project_id=project.id, keyword="BRAND", match_type="exact_word")
        db.add_all([kw1, kw2])
        db.flush()

        assert len(project.keywords) == 2
        assert kw1.match_type == "contains"  # default
        assert kw2.match_type == "exact_word"

    def test_project_keyword_cascade_delete(self, db):
        project = Project(name="Cascade Test", slug="cascade-test-model")
        db.add(project)
        db.flush()

        kw = ProjectKeyword(project_id=project.id, keyword="test")
        db.add(kw)
        db.flush()

        project_id = project.id
        db.delete(project)
        db.flush()

        remaining = db.query(ProjectKeyword).filter(ProjectKeyword.project_id == project_id).all()
        assert len(remaining) == 0


# ── API Tests ──


class TestProjectApi:
    def test_list_projects_empty(self):
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "projects" in data
        assert isinstance(data["projects"], list)

    def test_project_articles_not_found(self):
        response = client.get("/api/projects/nonexistent-slug/articles")
        assert response.status_code == 404

    def test_project_articles_with_data(self):
        """Create a project+keyword+article and verify the endpoint returns matching articles."""
        db = database.SessionLocal()
        try:
            # Create feed
            feed = Feed(name="ProjTestFeed", url="https://proj.com", rss_url="https://proj.com/rss")
            db.add(feed)
            db.flush()

            # Create article that matches keyword
            article = Article(
                feed_id=feed.id,
                title="Strabag wins major contract in Poland",
                url="https://example.com/strabag-contract",
                summary="Construction giant Strabag secures new infrastructure deal.",
                hash="strabag_test_hash_001",
            )
            db.add(article)

            # Create project + keyword
            project = Project(name="Strabag API Test", slug="strabag-api-test")
            db.add(project)
            db.flush()

            db.add(ProjectKeyword(project_id=project.id, keyword="Strabag"))
            db.commit()
        finally:
            db.close()

        # Test API
        response = client.get("/api/projects/strabag-api-test/articles")
        assert response.status_code == 200
        data = response.json()
        assert data["project"] == "Strabag API Test"
        assert data["total"] >= 1
        assert any("Strabag" in a["title"] for a in data["articles"])

    def test_project_articles_no_keywords(self):
        """A project with no keywords should return empty results."""
        db = database.SessionLocal()
        try:
            project = Project(name="Empty KW Project", slug="empty-kw-test")
            db.add(project)
            db.commit()
        finally:
            db.close()

        response = client.get("/api/projects/empty-kw-test/articles")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["articles"] == []

    def test_create_project_requires_auth(self):
        response = client.post("/api/projects", data={
            "name": "Unauth Project",
            "slug": "unauth-test",
        })
        assert response.status_code == 401

    def test_delete_project_requires_auth(self):
        response = client.delete("/api/projects/some-slug")
        assert response.status_code == 401
