"""Tests for SQLAlchemy models and DB relationships."""

from src.models import (
    Article,
    ArticleDepartment,
    Department,
    Feed,
    FeedDepartment,
    FetchLog,
)

# ── Feed CRUD ──


def test_create_feed(db):
    feed = Feed(name="Test Feed", url="https://test.com", rss_url="https://test.com/rss")
    db.add(feed)
    db.flush()
    assert feed.id is not None
    assert feed.is_active is True
    assert feed.fetch_interval == 30  # default


def test_feed_defaults(db):
    feed = Feed(name="Defaults", url="https://defaults.com", rss_url="https://defaults.com/rss")
    db.add(feed)
    db.flush()
    assert feed.feed_type == "rss"
    assert feed.is_active is True
    assert feed.last_fetched is None


# ── Department CRUD ──


def test_create_department(db):
    dept = Department(name="Science", slug="science", description="Science department")
    db.add(dept)
    db.flush()
    assert dept.id is not None
    assert dept.slug == "science"


# ── M2M: Feed <-> Department ──


def test_feed_department_relationship(db):
    feed = Feed(name="Nature", url="https://nature.com", rss_url="https://nature.com/rss")
    dept = Department(name="Science", slug="science-m2m-test")
    db.add_all([feed, dept])
    db.flush()

    fd = FeedDepartment(feed_id=feed.id, department_id=dept.id)
    db.add(fd)
    db.flush()

    # Query back
    result = db.query(FeedDepartment).filter_by(feed_id=feed.id).first()
    assert result is not None
    assert result.department_id == dept.id


# ── Article CRUD ──


def test_create_article(db):
    feed = Feed(name="Feed", url="https://f.com", rss_url="https://f.com/rss")
    db.add(feed)
    db.flush()

    article = Article(
        feed_id=feed.id,
        title="Test Article",
        url="https://example.com/test",
        hash="abc123def456",
    )
    db.add(article)
    db.flush()

    assert article.id is not None
    assert article.sent_to_saas is False


def test_article_feed_relationship(db):
    feed = Feed(name="RelFeed", url="https://rel.com", rss_url="https://rel.com/rss")
    db.add(feed)
    db.flush()

    article = Article(
        feed_id=feed.id,
        title="Rel Article",
        url="https://rel.com/article",
        hash="rel_hash_unique",
    )
    db.add(article)
    db.flush()

    assert article.feed.name == "RelFeed"


# ── M2M: Article <-> Department ──


def test_article_department_tagging(db):
    feed = Feed(name="TagFeed", url="https://tag.com", rss_url="https://tag.com/rss")
    dept1 = Department(name="Dept1", slug="dept1-tag-test")
    dept2 = Department(name="Dept2", slug="dept2-tag-test")
    db.add_all([feed, dept1, dept2])
    db.flush()

    article = Article(
        feed_id=feed.id,
        title="Multi-dept Article",
        url="https://tag.com/multi",
        hash="multi_dept_hash",
    )
    db.add(article)
    db.flush()

    # Tag with both departments
    db.add(ArticleDepartment(article_id=article.id, department_id=dept1.id))
    db.add(ArticleDepartment(article_id=article.id, department_id=dept2.id))
    db.flush()

    tags = db.query(ArticleDepartment).filter_by(article_id=article.id).all()
    assert len(tags) == 2


# ── FetchLog ──


def test_create_fetch_log(db):
    feed = Feed(name="LogFeed", url="https://log.com", rss_url="https://log.com/rss")
    db.add(feed)
    db.flush()

    log = FetchLog(feed_id=feed.id, status="success", articles_found=5, articles_new=3)
    db.add(log)
    db.flush()

    assert log.id is not None
    assert log.status == "success"
    assert log.articles_new == 3
    assert log.error_message is None


def test_fetch_log_error(db):
    feed = Feed(name="ErrFeed", url="https://err.com", rss_url="https://err.com/rss")
    db.add(feed)
    db.flush()

    log = FetchLog(feed_id=feed.id, status="error", articles_found=0, error_message="Timeout")
    db.add(log)
    db.flush()

    assert log.status == "error"
    assert log.error_message == "Timeout"
