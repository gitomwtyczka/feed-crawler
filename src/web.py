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

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func

from . import database as db_module
from .auth import (
    authenticate_user,
    create_access_token,
    decode_access_token,
    ensure_default_admin,
)
from .crawl_state import get_state as get_crawl_state
from .crawl_state import toggle_crawl
from .models import SOURCE_TIERS, Article, Department, Feed

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
templates.env.globals["SOURCE_TIERS"] = SOURCE_TIERS

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


# ── Auth Helpers ──


def _get_current_user(request: Request) -> str | None:
    """Get current admin user from JWT cookie. Returns username or None."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    return decode_access_token(token)


# ── Startup ──


@app.on_event("startup")
def on_startup():
    db_module.init_db()
    # Create default admin user if none exist
    db = db_module.SessionLocal()
    try:
        ensure_default_admin(db)
    finally:
        db.close()


# ── Reader Routes ──


@app.get("/", response_class=HTMLResponse)
def reader_home(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
    tier: int = Query(0, ge=0, le=5),
):
    """Latest articles from all feeds."""
    db = db_module.SessionLocal()
    try:
        offset = (page - 1) * per_page
        q = db.query(Article)
        count_q = db.query(func.count(Article.id))
        if tier:
            q = q.join(Feed).filter(Feed.source_tier == tier)
            count_q = count_q.join(Feed).filter(Feed.source_tier == tier)
        total = count_q.scalar()
        articles = (
            q.order_by(desc(func.coalesce(Article.published_at, Article.fetched_at)))
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
            "current_tier": tier,
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
            .order_by(desc(func.coalesce(Article.published_at, Article.fetched_at)))
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
            # Multi-word AND search: each word must appear somewhere
            # Searches: article title, summary, content, author, AND feed name
            from sqlalchemy import and_, or_

            words = q.strip().split()
            conditions = []
            for word in words[:10]:  # limit to 10 words
                w = f"%{word}%"
                conditions.append(or_(
                    Article.title.ilike(w),
                    Article.summary.ilike(w),
                    Article.content.ilike(w),
                    Article.author.ilike(w),
                    Feed.name.ilike(w),
                ))
            query = (
                db.query(Article)
                .outerjoin(Feed, Article.feed_id == Feed.id)
                .filter(and_(*conditions))
            ) if conditions else db.query(Article)
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


# ── Auth Routes ──


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    user = _get_current_user(request)
    if user:
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    db = db_module.SessionLocal()
    try:
        user = authenticate_user(db, username, password)
        if not user:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Nieprawidłowy login lub hasło",
            })
        token = create_access_token(user.username)
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie("access_token", token, httponly=True, max_age=86400)
        return response
    finally:
        db.close()


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    return response


# ── Admin Routes (auth required) ──


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
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
            "user": user,
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


@app.get("/admin/monitoring", response_class=HTMLResponse)
def admin_monitoring(request: Request):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    db = db_module.SessionLocal()
    try:
        from .models import FetchLog

        total_feeds = db.query(func.count(Feed.id)).scalar()
        active_feeds = db.query(func.count(Feed.id)).filter(Feed.is_active).scalar()
        disabled_feeds = total_feeds - active_feeds

        # Feeds with errors (sorted by error count desc)
        error_feeds = (
            db.query(Feed)
            .filter(Feed.consecutive_errors > 0)
            .order_by(desc(Feed.consecutive_errors))
            .all()
        )

        # Disabled feeds
        disabled_list = (
            db.query(Feed)
            .filter(Feed.is_active == False)  # noqa: E712
            .order_by(desc(Feed.consecutive_errors))
            .all()
        )

        # Recent fetch logs (last 50)
        recent_logs = (
            db.query(FetchLog)
            .order_by(desc(FetchLog.started_at))
            .limit(50)
            .all()
        )

        # Health score
        health_pct = round((active_feeds / total_feeds * 100) if total_feeds else 0, 1)

        # Crawl state
        crawl_state = get_crawl_state()

        return templates.TemplateResponse("admin/monitoring.html", {
            "request": request,
            "user": user,
            "total_feeds": total_feeds,
            "active_feeds": active_feeds,
            "disabled_feeds": disabled_feeds,
            "error_feeds": error_feeds,
            "disabled_list": disabled_list,
            "recent_logs": recent_logs,
            "health_pct": health_pct,
            "crawl_enabled": crawl_state.get("crawl_enabled", False),
            "crawl_interval": crawl_state.get("crawl_interval_minutes", 10),
        })
    finally:
        db.close()


@app.post("/admin/crawl/toggle")
def admin_crawl_toggle(request: Request):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    new_state = toggle_crawl()
    import logging
    logging.getLogger(__name__).info("Crawl toggled to %s by %s", new_state, user)
    return RedirectResponse(url="/admin/monitoring", status_code=303)


@app.get("/admin/settings", response_class=HTMLResponse)
def admin_settings_page(request: Request, saved: bool = False):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    from .admin_settings import get_settings

    return templates.TemplateResponse("admin/settings.html", {
        "request": request,
        "user": user,
        "settings": get_settings(),
        "saved": saved,
    })


@app.post("/admin/settings")
def admin_settings_save(
    request: Request,
    isbnews_username: str = Form(""),
    isbnews_password: str = Form(""),
    newseria_username: str = Form(""),
    newseria_password: str = Form(""),
    discord_crawler_webhook_url: str = Form(""),
    saas_webhook_url: str = Form(""),
    saas_webhook_api_key: str = Form(""),
):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    from .admin_settings import update_settings

    update_settings({
        "isbnews_username": isbnews_username,
        "isbnews_password": isbnews_password,
        "newseria_username": newseria_username,
        "newseria_password": newseria_password,
        "discord_crawler_webhook_url": discord_crawler_webhook_url,
        "saas_webhook_url": saas_webhook_url,
        "saas_webhook_api_key": saas_webhook_api_key,
    })
    return RedirectResponse(url="/admin/settings?saved=true", status_code=303)


# ── User Management Routes ──


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(
    request: Request,
    message: str = Query(""),
    error: str = Query(""),
):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Admin-only guard
    db = db_module.SessionLocal()
    try:
        from .auth import get_admin_user, has_permission, list_users

        admin_user = get_admin_user(db, user)
        if not admin_user or not has_permission(admin_user.role or "viewer", "admin"):
            return RedirectResponse(url="/admin", status_code=303)

        users = list_users(db)
        return templates.TemplateResponse("admin/users.html", {
            "request": request,
            "user": user,
            "current_user": user,
            "users": users,
            "message": message,
            "error": error,
        })
    finally:
        db.close()


@app.post("/admin/users")
def admin_users_create(
    request: Request,
    username: str = Form(...),
    email: str = Form(""),
    password: str = Form(...),
    role: str = Form("viewer"),
):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    db = db_module.SessionLocal()
    try:
        from .auth import create_user, get_admin_user, has_permission

        admin_user = get_admin_user(db, user)
        if not admin_user or not has_permission(admin_user.role or "viewer", "admin"):
            return RedirectResponse(url="/admin", status_code=303)

        try:
            create_user(db, username=username, password=password, role=role, email=email)
            return RedirectResponse(
                url=f"/admin/users?message=Utworzono+konto+{username}",
                status_code=303,
            )
        except Exception as e:
            return RedirectResponse(
                url=f"/admin/users?error={e!s}",
                status_code=303,
            )
    finally:
        db.close()


@app.post("/admin/users/{user_id}/edit")
def admin_users_edit(
    request: Request,
    user_id: int,
    email: str = Form(""),
    role: str = Form("viewer"),
    password: str = Form(""),
    is_active: str = Form(""),
):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    db = db_module.SessionLocal()
    try:
        from .auth import get_admin_user, has_permission, update_user

        admin_user = get_admin_user(db, user)
        if not admin_user or not has_permission(admin_user.role or "viewer", "admin"):
            return RedirectResponse(url="/admin", status_code=303)

        update_user(
            db, user_id,
            email=email,
            role=role,
            password=password if password else None,
            is_active=bool(is_active),
        )
        return RedirectResponse(url="/admin/users?message=Zaktualizowano+konto", status_code=303)
    finally:
        db.close()


@app.post("/admin/users/{user_id}/delete")
def admin_users_delete(request: Request, user_id: int):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    db = db_module.SessionLocal()
    try:
        from .auth import delete_user, get_admin_user, has_permission

        admin_user = get_admin_user(db, user)
        if not admin_user or not has_permission(admin_user.role or "viewer", "admin"):
            return RedirectResponse(url="/admin", status_code=303)

        if delete_user(db, user_id):
            return RedirectResponse(url="/admin/users?message=Usunięto+konto", status_code=303)
        return RedirectResponse(
            url="/admin/users?error=Nie+można+usunąć+ostatniego+admina",
            status_code=303,
        )
    finally:
        db.close()


@app.get("/admin/discover", response_class=HTMLResponse)
def admin_discover_page(request: Request):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("admin/discover.html", {
        "request": request,
        "user": user,
        "results": None,
        "url": "",
    })


@app.post("/admin/discover", response_class=HTMLResponse)
async def admin_discover_run(request: Request, url: str = Form("")):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    results = []
    if url.strip():

        from .feed_evaluator import evaluate_feed
        from .feed_scout import discover_feeds

        # Get existing feed URLs for uniqueness check
        db = db_module.SessionLocal()
        try:
            existing = {f.rss_url for f in db.query(Feed.rss_url).all() if f.rss_url}
        finally:
            db.close()

        # Discover feeds from URL
        discovered = await discover_feeds(url.strip())

        # Evaluate each discovered feed
        for feed in discovered:
            score = await evaluate_feed(feed.url, existing)
            results.append({
                "url": feed.url,
                "title": score.title or feed.title,
                "score": score.overall_score,
                "activity": score.activity_score,
                "quality": score.quality_score,
                "reliability": score.reliability_score,
                "uniqueness": score.uniqueness_score,
                "recommendation": score.recommendation,
                "articles_count": score.articles_count,
                "articles_per_day": score.articles_per_day,
                "sample_titles": score.sample_titles or feed.sample_titles,
                "sample_links": score.sample_links or getattr(feed, "sample_links", []),
                "site_url": getattr(feed, "source_domain", ""),
                "discovery_method": feed.discovery_method,
                "already_exists": feed.url in existing,
            })

        # Sort by score desc
        results.sort(key=lambda r: r["score"], reverse=True)

    return templates.TemplateResponse("admin/discover.html", {
        "request": request,
        "user": user,
        "results": results,
        "url": url,
    })


@app.post("/admin/discover/add")
def admin_discover_add(request: Request, feed_url: str = Form(...), feed_name: str = Form("")):
    """Add a discovered feed directly to the database."""
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    db = db_module.SessionLocal()
    try:
        # Check if already exists
        existing = db.query(Feed).filter(Feed.rss_url == feed_url).first()
        if existing:
            return RedirectResponse(url="/admin/discover", status_code=303)

        name = feed_name or feed_url.split("/")[2]  # use domain as fallback
        feed = Feed(
            name=name,
            rss_url=feed_url,
            url=f"https://{feed_url.split('/')[2]}",
            is_active=True,
            fetch_interval=30,
        )
        db.add(feed)
        db.commit()
    finally:
        db.close()

    return RedirectResponse(url="/admin/feeds", status_code=303)


@app.get("/admin/feeds", response_class=HTMLResponse)
def admin_feeds(request: Request, page: int = Query(1, ge=1)):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
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
            "user": user,
            "feeds": feeds,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        })
    finally:
        db.close()


@app.post("/admin/feeds/{feed_id}/toggle")
def admin_toggle_feed(request: Request, feed_id: int):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
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
                    "consecutive_errors": f.consecutive_errors or 0,
                    "backoff_until": f.backoff_until.isoformat() if f.backoff_until else None,
                }
                for f in feeds
            ],
        }
    finally:
        db.close()


# ── Export API ──


@app.get("/api/export")
def api_export(
    format: str = Query("json", description="Export format: json or csv"),
    department: str = Query(None, description="Filter by department slug"),
    feed_id: int = Query(None, description="Filter by feed ID"),
    limit: int = Query(1000, le=10000, description="Max articles to export"),
):
    """Export articles as JSON or CSV with optional filtering."""
    import csv
    import io

    db = db_module.SessionLocal()
    try:
        query = db.query(Article).order_by(desc(Article.published_at))

        if department:
            dept = db.query(Department).filter(Department.slug == department).first()
            if dept:
                query = query.filter(Article.departments.any(Department.id == dept.id))

        if feed_id:
            query = query.filter(Article.feed_id == feed_id)

        articles = query.limit(limit).all()

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["id", "title", "url", "author", "published_at", "feed_name", "departments"])
            for a in articles:
                writer.writerow([
                    a.id,
                    a.title,
                    a.url,
                    a.author or "",
                    a.published_at.isoformat() if a.published_at else "",
                    a.feed.name if a.feed else "",
                    "|".join(d.slug for d in a.departments),
                ])
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=articles_export.csv"},
            )

        # JSON format (default)
        return {
            "total": len(articles),
            "articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "url": a.url,
                    "summary": a.summary or "",
                    "content": a.content or "",
                    "author": a.author or "",
                    "published_at": a.published_at.isoformat() if a.published_at else None,
                    "fetched_at": a.fetched_at.isoformat() if a.fetched_at else None,
                    "feed_name": a.feed.name if a.feed else "",
                    "departments": [d.slug for d in a.departments],
                }
                for a in articles
            ],
        }
    finally:
        db.close()


@app.get("/api/health")
def api_health():
    """System health endpoint with feed error stats."""
    db = db_module.SessionLocal()
    try:
        total_feeds = db.query(func.count(Feed.id)).scalar()
        active_feeds = db.query(func.count(Feed.id)).filter(Feed.is_active).scalar()
        total_articles = db.query(func.count(Article.id)).scalar()

        # Feeds with errors
        feeds_with_errors = (
            db.query(Feed)
            .filter(Feed.consecutive_errors > 0)
            .order_by(desc(Feed.consecutive_errors))
            .limit(20)
            .all()
        )

        return {
            "status": "healthy",
            "feeds_total": total_feeds,
            "feeds_active": active_feeds,
            "feeds_disabled": total_feeds - active_feeds,
            "articles_total": total_articles,
            "feeds_with_errors": [
                {
                    "id": f.id,
                    "name": f.name,
                    "consecutive_errors": f.consecutive_errors,
                    "backoff_until": f.backoff_until.isoformat() if f.backoff_until else None,
                    "is_active": f.is_active,
                }
                for f in feeds_with_errors
            ],
        }
    finally:
        db.close()

