---
feature_id: "2.0"
status: pending
assigned: worker
created: 2026-03-12
priority: high
---

# Per-Brand Project Tracking (Model + API)

## Problem
Klienci (agencje PR, korporacje) potrzebują monitorować konkretne marki/tematy.
Np. agencja PR obsługuje Strabag → chce widzieć WSZYSTKIE artykuły o Strabag,
z podziałem na oryginały/przedruki, sentyment, AVE.

Bez tego nie ma monetyzacji dla segmentu PR (499-1499 PLN/mies).

## Lokalizacja kodu

### Istniejące:
- `src/models.py` — modele SQLAlchemy (Feed, Article, Department)
- `src/web.py` — Flask routes (API + HTML)
- `src/database.py` — SessionLocal, Base

### Nowe pliki:
- `src/models.py` — dodaj klasy `Project`, `ProjectKeyword` (MODIFY)
- `templates/admin/projects.html` — [NEW] panel zarządzania projektami

## Implementacja

### Krok 1: Dodaj modele w `src/models.py`

Po klasie `ArticleDepartment` dodaj:

```python
class Project(Base):
    """Brand monitoring project — tracks a brand/topic across all sources."""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, doc="Project name, e.g. 'Strabag'")
    slug = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    keywords = relationship("ProjectKeyword", back_populates="project", cascade="all, delete-orphan")


class ProjectKeyword(Base):
    """Keyword to match articles against a project."""
    __tablename__ = "project_keywords"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    keyword = Column(String(255), nullable=False, doc="Keyword to search for (case-insensitive)")
    match_type = Column(String(20), nullable=False, default="contains", doc="contains | exact_word | regex")

    # Relationships
    project = relationship("Project", back_populates="keywords")
```

### Krok 2: API endpoint w `src/web.py`

Dodaj endpoint `/api/projects/<slug>/articles`:

```python
@app.get("/api/projects/{slug}/articles")
async def project_articles(slug: str, limit: int = 50, offset: int = 0):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.slug == slug).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        keywords = [kw.keyword for kw in project.keywords]
        
        # Build OR filter for all keywords
        from sqlalchemy import or_
        filters = []
        for kw in keywords:
            filters.append(Article.title.ilike(f"%{kw}%"))
            filters.append(Article.summary.ilike(f"%{kw}%"))
        
        articles = (
            db.query(Article)
            .filter(or_(*filters))
            .order_by(Article.fetched_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        total = db.query(func.count(Article.id)).filter(or_(*filters)).scalar()
        
        return {
            "project": project.name,
            "total": total,
            "articles": [
                {
                    "id": a.id,
                    "title": a.title,
                    "url": a.url,
                    "source": a.feed.name if a.feed else None,
                    "published_at": str(a.published_at) if a.published_at else None,
                    "ai_category": a.ai_category,
                    "ai_sentiment": a.ai_sentiment,
                    "reprint_type": a.reprint_type,
                    "similarity_score": a.similarity_score,
                }
                for a in articles
            ],
        }
    finally:
        db.close()
```

### Krok 3: Migracja DB

```sql
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_keywords (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    keyword VARCHAR(255) NOT NULL,
    match_type VARCHAR(20) NOT NULL DEFAULT 'contains'
);
```

### Krok 4: Seed z testowymi projektami

```python
# Testowe projekty
SEED_PROJECTS = [
    {"name": "Strabag", "slug": "strabag", "keywords": ["Strabag", "STRABAG"]},
    {"name": "Orlen", "slug": "orlen", "keywords": ["Orlen", "PKN Orlen", "ORLEN"]},
    {"name": "PZU", "slug": "pzu", "keywords": ["PZU", "Powszechny Zakład Ubezpieczeń"]},
    {"name": "TVP", "slug": "tvp", "keywords": ["TVP", "Telewizja Polska"]},
]
```

## Kryteria gotowości
- [ ] Modele `Project` + `ProjectKeyword` dodane do `models.py`
- [ ] Tabele `projects` + `project_keywords` w DB (migration)
- [ ] Endpoint API `/api/projects/{slug}/articles` działa
- [ ] Seed z 4 testowymi projektami
- [ ] Test: GET `/api/projects/strabag/articles` zwraca artykuły
- [ ] Deploy na VPS

## Uwagi
- **NIE ruszaj** istniejących modeli (Feed, Article, Department)
- **NIE ruszaj** schedulera — project matching jest query-time, nie processing-time
- Import `Project` w `web.py` — dodaj do istniejącego importu z `models`
- ILIKE jest case-insensitive w PostgreSQL — to nas interesuje
