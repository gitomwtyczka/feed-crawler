"""
Feed Crawler Admin Panel + Reader — FastAPI Application.

Endpoints:
  Admin:
    GET /admin              → Dashboard (stats, recent activity)
    GET /admin/feeds        → Feed list (status, article count, last fetch)
    GET /admin/feeds/{id}   → Feed detail (articles, fetch logs)
    POST /admin/feeds/{id}/toggle → Enable/disable feed
    GET /admin/departments  → Department overview

  Reader:
    GET /                   → Latest articles (all feeds)
    GET /feed/{id}          → Articles from specific feed
    GET /department/{slug}  → Articles by department
    GET /article/{id}       → Full article view
    GET /search             → Search articles

  API:
    GET /api/stats          → JSON stats
    GET /api/articles       → JSON article list (paginated)
    GET /api/feeds          → JSON feed list
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func

from . import database as db_module
from .models import Article, Department, Feed

# ── App Setup ──

app = FastAPI(
    title="Feed Crawler",
    description="AI-powered news aggregation platform",
    version="0.1.0",
)

BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_db():
    db = db_module.SessionLocal()
    try:
        return db
    finally:
        pass  # caller must close


# ── Jinja2 Filters ──


def timeago(dt: datetime | None) -> str:
    if not dt:
        return "never"
    now = datetime.utcnow()
    delta = now - dt
    if delta.seconds < 60:
        return "just now"
    if delta.seconds < 3600:
        return f"{delta.seconds // 60}m ago"
    if delta.seconds < 86400:
        return f"{delta.seconds // 3600}h ago"
    return f"{delta.days}d ago"


def truncate(text: str | None, length: int = 200) -> str:
    if not text:
        return ""
    return text[:length] + "..." if len(text) > length else text


templates.env.filters["timeago"] = timeago
templates.env.filters["truncate"] = truncate


# ── Startup ──


@app.on_event("startup")
def on_startup():
    db_module.init_db()


# ── Reader Routes ──


@app.get("/", response_class=HTMLResponse)
def reader_home(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
):
    """Latest articles from all feeds."""
    db = db_module.SessionLocal()
    try:
        offset = (page - 1) * per_page
        total = db.query(func.count(Article.id)).scalar()
        articles = (
            db.query(Article)
            .order_by(desc(Article.published_at), desc(Article.fetched_at))
            .offset(offset)
            .limit(per_page)
            .all()
        )
        total_pages = (total + per_page - 1) // per_page
        return templates.TemplateResponse("reader/home.html", {
            "request": request,
            "articles": articles,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "per_page": per_page,
        })
    finally:
        db.close()


@app.get("/feed/{feed_id}", response_class=HTMLResponse)
def reader_feed(request: Request, feed_id: int, page: int = Query(1, ge=1)):
    db = db_module.SessionLocal()
    try:
        feed = db.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            return HTMLResponse("Feed not found", status_code=404)

        per_page = 50
        offset = (page - 1) * per_page
        total = db.query(func.count(Article.id)).filter(Article.feed_id == feed_id).scalar()
        articles = (
            db.query(Article)
            .filter(Article.feed_id == feed_id)
            .order_by(desc(Article.published_at))
            .offset(offset)
            .limit(per_page)
            .all()
        )
        total_pages = (total + per_page - 1) // per_page
        return templates.TemplateResponse("reader/feed.html", {
            "request": request,
            "feed": feed,
            "articles": articles,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        })
    finally:
        db.close()


@app.get("/department/{slug}", response_class=HTMLResponse)
def reader_department(request: Request, slug: str, page: int = Query(1, ge=1)):
    db = db_module.SessionLocal()
    try:
        dept = db.query(Department).filter(Department.slug == slug).first()
        if not dept:
            return HTMLResponse("Department not found", status_code=404)

        per_page = 50
        offset = (page - 1) * per_page
        feed_ids = [f.id for f in dept.feeds]
        total = db.query(func.count(Article.id)).filter(Article.feed_id.in_(feed_ids)).scalar() if feed_ids else 0
        articles = (
            db.query(Article)
            .filter(Article.feed_id.in_(feed_ids))
            .order_by(desc(Article.published_at))
            .offset(offset)
            .limit(per_page)
            .all()
        ) if feed_ids else []
        total_pages = max(1, (total + per_page - 1) // per_page)
        return templates.TemplateResponse("reader/department.html", {
            "request": request,
            "department": dept,
            "articles": articles,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        })
    finally:
        db.close()


@app.get("/article/{article_id}", response_class=HTMLResponse)
def reader_article(request: Request, article_id: int):
    db = db_module.SessionLocal()
    try:
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            return HTMLResponse("Article not found", status_code=404)
        return templates.TemplateResponse("reader/article.html", {
            "request": request,
            "article": article,
        })
    finally:
        db.close()


@app.get("/search", response_class=HTMLResponse)
def reader_search(request: Request, q: str = Query(""), page: int = Query(1, ge=1)):
    db = db_module.SessionLocal()
    try:
        per_page = 50
        offset = (page - 1) * per_page
        if q:
            query = db.query(Article).filter(
                Article.title.ilike(f"%{q}%") | Article.summary.ilike(f"%{q}%")
            )
        else:
            query = db.query(Article)

        total = query.count()
        articles = query.order_by(desc(Article.published_at)).offset(offset).limit(per_page).all()
        total_pages = max(1, (total + per_page - 1) // per_page)
        return templates.TemplateResponse("reader/search.html", {
            "request": request,
            "articles": articles,
            "q": q,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        })
    finally:
        db.close()


# ── Admin Routes ──


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    db = db_module.SessionLocal()
    try:
        total_feeds = db.query(func.count(Feed.id)).scalar()
        active_feeds = db.query(func.count(Feed.id)).filter(Feed.is_active).scalar()
        total_articles = db.query(func.count(Article.id)).scalar()
        total_departments = db.query(func.count(Department.id)).scalar()

        # Articles in last 24h
        yesterday = datetime.utcnow() - timedelta(hours=24)
        articles_24h = db.query(func.count(Article.id)).filter(Article.fetched_at >= yesterday).scalar()

        # Top feeds by article count
        top_feeds = (
            db.query(Feed.id, Feed.name, func.count(Article.id).label("count"))
            .join(Article, Article.feed_id == Feed.id)
            .group_by(Feed.id, Feed.name)
            .order_by(desc("count"))
            .limit(10)
            .all()
        )

        # Recent articles
        recent = db.query(Article).order_by(desc(Article.fetched_at)).limit(15).all()

        # Departments with feed counts
        departments = db.query(Department).all()
        dept_stats = []
        for dept in departments:
            feed_count = len(dept.feeds)
            dept_stats.append({"name": dept.name, "slug": dept.slug, "feeds": feed_count})

        return templates.TemplateResponse("admin/dashboard.html", {
            "request": request,
            "total_feeds": total_feeds,
            "active_feeds": active_feeds,
            "total_articles": total_articles,
            "total_departments": total_departments,
            "articles_24h": articles_24h,
            "top_feeds": top_feeds,
            "recent": recent,
            "dept_stats": dept_stats,
        })
    finally:
        db.close()


@app.get("/admin/feeds", response_class=HTMLResponse)
def admin_feeds(request: Request, page: int = Query(1, ge=1)):
    db = db_module.SessionLocal()
    try:
        per_page = 50
        offset = (page - 1) * per_page
        total = db.query(func.count(Feed.id)).scalar()

        feeds_raw = (
            db.query(
                Feed,
                func.count(Article.id).label("article_count"),
            )
            .outerjoin(Article, Article.feed_id == Feed.id)
            .group_by(Feed.id)
            .order_by(desc("article_count"))
            .offset(offset)
            .limit(per_page)
            .all()
        )

        feeds = [{"feed": f, "article_count": c} for f, c in feeds_raw]
        total_pages = max(1, (total + per_page - 1) // per_page)

        return templates.TemplateResponse("admin/feeds.html", {
            "request": request,
            "feeds": feeds,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        })
    finally:
        db.close()


@app.post("/admin/feeds/{feed_id}/toggle")
def admin_toggle_feed(feed_id: int):
    db = db_module.SessionLocal()
    try:
        feed = db.query(Feed).filter(Feed.id == feed_id).first()
        if feed:
            feed.is_active = not feed.is_active
            db.commit()
        return RedirectResponse(url="/admin/feeds", status_code=303)
    finally:
        db.close()


# ── API Routes ──


@app.get("/api/stats")
def api_stats():
    db = db_module.SessionLocal()
    try:
        yesterday = datetime.utcnow() - timedelta(hours=24)
        return {
            "total_feeds": db.query(func.count(Feed.id)).scalar(),
            "active_feeds": db.query(func.count(Feed.id)).filter(Feed.is_active).scalar(),
            "total_articles": db.query(func.count(Article.id)).scalar(),
            "articles_24h": db.query(func.count(Article.id)).filter(Article.fetched_at >= yesterday).scalar(),
            "departments": db.query(func.count(Department.id)).scalar(),
        }
    finally:
        db.close()


@app.get("/api/articles")
def api_articles(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100)):
    db = db_module.SessionLocal()
    try:
        offset = (page - 1) * per_page
        total = db.query(func.count(Article.id)).scalar()
        articles = (
            db.query(Article)
            .order_by(desc(Article.published_at))
            .offset(offset)
            .limit(per_page)
            .all()
        )
        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "url": a.url,
                    "summary": a.summary[:300] if a.summary else None,
                    "author": a.author,
                    "published_at": a.published_at.isoformat() if a.published_at else None,
                    "feed_name": a.feed.name if a.feed else None,
                }
                for a in articles
            ],
        }
    finally:
        db.close()


@app.get("/api/feeds")
def api_feeds():
    db = db_module.SessionLocal()
    try:
        feeds = db.query(Feed).all()
        return {
            "total": len(feeds),
            "feeds": [
                {
                    "id": f.id,
                    "name": f.name,
                    "rss_url": f.rss_url,
                    "feed_type": f.feed_type,
                    "is_active": f.is_active,
                    "last_fetched": f.last_fetched.isoformat() if f.last_fetched else None,
                    "article_count": len(f.articles),
                }
                for f in feeds
            ],
        }
    finally:
        db.close()
