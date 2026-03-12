"""
Client Monitoring Panel — FastAPI Routes.

Endpoints:
    GET  /client/login            → Client login page
    POST /client/login            → Handle client auth
    GET  /client/dashboard        → Dashboard: projects list + stats
    GET  /client/project/{slug}   → Project articles with reprint, sentiment
    GET  /client/logout           → Clear client cookie

Separate auth from admin (client_token cookie).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy import desc, func

from . import database as db_module
from .auth import create_access_token, decode_access_token, hash_password, verify_password
from .models import Article, Feed, Project, ProjectKeyword

logger = logging.getLogger(__name__)

CLIENT_COOKIE = "client_token"

router = APIRouter(prefix="/client", tags=["client"])


# ── Auth helpers ──


def _get_current_client(request: Request) -> dict | None:
    """Get current client from JWT cookie. Returns {username, id} or None."""
    token = request.cookies.get(CLIENT_COOKIE)
    if not token:
        return None
    username = decode_access_token(token)
    if not username:
        return None

    # Lazy import to avoid circular deps until model exists
    try:
        from .models import ClientAccount
    except ImportError:
        return None

    db = db_module.SessionLocal()
    try:
        client = db.query(ClientAccount).filter(
            ClientAccount.username == username,
            ClientAccount.is_active == True,  # noqa: E712
        ).first()
        if not client:
            return None
        return {
            "id": client.id,
            "username": client.username,
            "company_name": client.company_name,
            "tier": client.tier,
        }
    finally:
        db.close()


# ── Login ──


@router.get("/login", response_class=HTMLResponse)
def client_login_page(request: Request):
    """Client login form."""
    from pathlib import Path
    templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

    if _get_current_client(request):
        return RedirectResponse(url="/client/dashboard", status_code=302)
    return templates.TemplateResponse("client/login.html", {"request": request, "error": ""})


@router.post("/login")
def client_login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    """Handle client login."""
    from pathlib import Path
    templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

    try:
        from .models import ClientAccount
    except ImportError:
        return templates.TemplateResponse(
            "client/login.html",
            {"request": request, "error": "System w trakcie konfiguracji"},
            status_code=503,
        )

    db = db_module.SessionLocal()
    try:
        client = db.query(ClientAccount).filter(
            ClientAccount.username == username,
            ClientAccount.is_active == True,  # noqa: E712
        ).first()

        if not client or not verify_password(password, client.password_hash):
            return templates.TemplateResponse(
                "client/login.html",
                {"request": request, "error": "Nieprawidłowy login lub hasło"},
                status_code=401,
            )

        token = create_access_token(client.username)
        response = RedirectResponse(url="/client/dashboard", status_code=302)
        response.set_cookie(
            key=CLIENT_COOKIE,
            value=token,
            httponly=True,
            max_age=86400,  # 24h
            samesite="lax",
        )
        logger.info("Client login: %s (%s)", client.username, client.company_name)
        return response
    finally:
        db.close()


# ── Dashboard ──


@router.get("/dashboard", response_class=HTMLResponse)
def client_dashboard(request: Request):
    """Client dashboard — list of projects with stats."""
    from pathlib import Path
    templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
    templates.env.filters["timeago"] = _timeago
    templates.env.filters["source_domain"] = _source_domain

    client = _get_current_client(request)
    if not client:
        return RedirectResponse(url="/client/login", status_code=302)

    db = db_module.SessionLocal()
    try:
        # Get client's projects with article counts
        projects = db.query(Project).filter(
            Project.client_id == client["id"],
            Project.is_active == True,  # noqa: E712
        ).all()

        project_stats = []
        for project in projects:
            # Get keywords for this project
            keywords = db.query(ProjectKeyword).filter(
                ProjectKeyword.project_id == project.id
            ).all()
            keyword_list = [kw.keyword for kw in keywords]

            # Count matching articles (last 7 days)
            week_ago = datetime.utcnow() - timedelta(days=7)
            day_ago = datetime.utcnow() - timedelta(days=1)

            total_articles = _count_articles_for_keywords(db, keyword_list)
            articles_24h = _count_articles_for_keywords(db, keyword_list, since=day_ago)
            articles_7d = _count_articles_for_keywords(db, keyword_list, since=week_ago)

            # Sentiment breakdown (last 7 days)
            sentiment = _get_sentiment_breakdown(db, keyword_list, since=week_ago)

            # Reprint stats
            reprint_stats = _get_reprint_stats(db, keyword_list, since=week_ago)

            project_stats.append({
                "project": project,
                "keywords": keyword_list,
                "total_articles": total_articles,
                "articles_24h": articles_24h,
                "articles_7d": articles_7d,
                "sentiment": sentiment,
                "reprint_stats": reprint_stats,
            })

        # Generate AI brief for dashboard
        ai_brief = _generate_dashboard_brief(project_stats)

        return templates.TemplateResponse("client/dashboard.html", {
            "request": request,
            "client": client,
            "project_stats": project_stats,
            "ai_brief": ai_brief,
        })
    finally:
        db.close()


# ── Project Detail ──


@router.get("/project/{slug}", response_class=HTMLResponse)
def client_project_view(
    request: Request,
    slug: str,
    page: int = Query(1, ge=1),
    days: int = Query(7, ge=1, le=365),
    sentiment: str = Query("", regex="^(positive|negative|neutral|mixed|)?$"),
    reprint: str = Query("", regex="^(original|reprint|modified_reprint|)?$"),
):
    """Client project detail — articles with filters."""
    from pathlib import Path
    templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
    templates.env.filters["timeago"] = _timeago
    templates.env.filters["source_domain"] = _source_domain

    client = _get_current_client(request)
    if not client:
        return RedirectResponse(url="/client/login", status_code=302)

    db = db_module.SessionLocal()
    try:
        project = db.query(Project).filter(
            Project.slug == slug,
            Project.client_id == client["id"],
        ).first()

        if not project:
            return RedirectResponse(url="/client/dashboard", status_code=302)

        # Get keywords
        keywords = db.query(ProjectKeyword).filter(
            ProjectKeyword.project_id == project.id
        ).all()
        keyword_list = [kw.keyword for kw in keywords]

        # Build query
        since = datetime.utcnow() - timedelta(days=days)
        per_page = 25

        query = db.query(Article).join(Feed, Article.feed_id == Feed.id)

        # Keyword filter (ILIKE for each keyword, OR them)
        from sqlalchemy import or_
        if keyword_list:
            keyword_filters = [Article.title.ilike(f"%{kw}%") for kw in keyword_list]
            query = query.filter(or_(*keyword_filters))

        # Date filter
        query = query.filter(Article.published_at >= since)

        # Sentiment filter
        if sentiment:
            query = query.filter(Article.ai_sentiment == sentiment)

        # Reprint filter
        if reprint:
            query = query.filter(Article.reprint_type == reprint)

        total = query.count()
        total_pages = max(1, (total + per_page - 1) // per_page)

        articles = query.order_by(desc(Article.published_at)).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        # Stats for this view
        sentiment_breakdown = _get_sentiment_breakdown(db, keyword_list, since=since)
        reprint_breakdown = _get_reprint_stats(db, keyword_list, since=since)

        return templates.TemplateResponse("client/project.html", {
            "request": request,
            "client": client,
            "project": project,
            "keywords": keyword_list,
            "articles": articles,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "days": days,
            "sentiment_filter": sentiment,
            "reprint_filter": reprint,
            "sentiment_breakdown": sentiment_breakdown,
            "reprint_breakdown": reprint_breakdown,
        })
    finally:
        db.close()


# ── Logout ──


@router.get("/logout")
def client_logout():
    """Clear client cookie."""
    response = RedirectResponse(url="/client/login", status_code=302)
    response.delete_cookie(CLIENT_COOKIE)
    return response


# ── Helper functions ──


def _timeago(dt: datetime | None) -> str:
    """Human-friendly time delta."""
    if not dt:
        return "never"
    delta = datetime.utcnow() - dt
    if delta.total_seconds() < 60:
        return "just now"
    if delta.total_seconds() < 3600:
        return f"{int(delta.total_seconds() // 60)}m ago"
    if delta.total_seconds() < 86400:
        return f"{int(delta.total_seconds() // 3600)}h ago"
    return f"{delta.days}d ago"


def _source_domain(url: str) -> str:
    """Extract clean domain from URL for source attribution.
    
    GNews articles have real portal URL, not google.com.
    e.g. 'https://www.parkiet.com/abc' → 'parkiet.com'
    """
    if not url:
        return "unknown"
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or ""
        # Strip www.
        if domain.startswith("www."):
            domain = domain[4:]
        return domain or "unknown"
    except Exception:
        return "unknown"


def _count_articles_for_keywords(
    db, keywords: list[str], since: datetime | None = None
) -> int:
    """Count articles matching any of the keywords."""
    if not keywords:
        return 0
    from sqlalchemy import or_
    query = db.query(func.count(Article.id))
    keyword_filters = [Article.title.ilike(f"%{kw}%") for kw in keywords]
    query = query.filter(or_(*keyword_filters))
    if since:
        query = query.filter(Article.published_at >= since)
    return query.scalar() or 0


def _get_sentiment_breakdown(
    db, keywords: list[str], since: datetime | None = None
) -> dict:
    """Get sentiment counts for matching articles."""
    if not keywords:
        return {}
    from sqlalchemy import or_
    query = db.query(
        Article.ai_sentiment, func.count(Article.id)
    )
    keyword_filters = [Article.title.ilike(f"%{kw}%") for kw in keywords]
    query = query.filter(or_(*keyword_filters))
    if since:
        query = query.filter(Article.published_at >= since)
    query = query.group_by(Article.ai_sentiment)
    return dict(query.all())


def _get_reprint_stats(
    db, keywords: list[str], since: datetime | None = None
) -> dict:
    """Get reprint type counts for matching articles."""
    if not keywords:
        return {}
    from sqlalchemy import or_
    query = db.query(
        Article.reprint_type, func.count(Article.id)
    )
    keyword_filters = [Article.title.ilike(f"%{kw}%") for kw in keywords]
    query = query.filter(or_(*keyword_filters))
    if since:
        query = query.filter(Article.published_at >= since)
    query = query.group_by(Article.reprint_type)
    return dict(query.all())


def _generate_dashboard_brief(project_stats: list[dict]) -> str:
    """Generate AI-style brief for dashboard header."""
    if not project_stats:
        return "Brak aktywnych projektów."

    lines = []
    for ps in project_stats:
        name = ps["project"].name
        h24 = ps["articles_24h"]
        h7d = ps["articles_7d"]
        sent = ps["sentiment"]

        # Dominant sentiment
        if sent:
            dominant = max(sent.items(), key=lambda x: x[1] if x[1] else 0)
            sent_label = {
                "positive": "pozytywny",
                "negative": "negatywny",
                "neutral": "neutralny",
                "mixed": "mieszany",
            }.get(dominant[0] or "neutral", "neutral")
            total_sent = sum(v for v in sent.values() if v)
            pct = int(dominant[1] / total_sent * 100) if total_sent else 0
        else:
            sent_label = "brak danych"
            pct = 0

        # Reprint info
        reprints = ps["reprint_stats"]
        originals = reprints.get("original", 0) or 0
        reprs = reprints.get("reprint", 0) or 0

        line = f"**{name}** — {h24} nowych wzmianek (24h), {h7d} w tygodniu."
        if pct > 0:
            line += f" Dominuje sentyment {sent_label} ({pct}%)."
        if reprs > 0:
            line += f" {reprs} przedruków, {originals} oryginałów."
        lines.append(line)

    return " | ".join(lines)
