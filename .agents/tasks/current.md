---
feature_id: "1.0"
status: pending
assigned: worker
created: 2026-03-12
priority: high
---

# Oryginał/Przedruk Detection Module

## Problem
Agencje PR potrzebują wiedzieć czy artykuł to oryginał, przedruk (copy-paste z innego portalu),
czy przedruk ze zmianami. To kluczowa metryka w monitoringu mediów (IMM to oferuje, my nie).

## Lokalizacja kodu

### Istniejący moduł:
- `src/dedup.py` — deduplikacja artykułów, liczy fingerprint tekstu (SimHash/MinHash)
- `src/models.py` — model `Article` z polami `title`, `summary`, `url`, `fetched_at`
- `src/feed_parser.py` — parsuje i zapisuje artykuły

### Nowe pliki:
- `src/reprint_detector.py` — [NEW] moduł detekcji oryginał/przedruk

## Implementacja

### Krok 1: Dodaj pola do modelu Article

W `src/models.py`, dodaj do klasy `Article`:
```python
reprint_type = Column(String(20), nullable=True)  # "original", "reprint", "modified_reprint"
original_article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
similarity_score = Column(Float, nullable=True)  # 0.0 - 1.0
```

### Krok 2: Stwórz `src/reprint_detector.py`

```python
"""
Reprint detection — classifies articles as original, reprint, or modified reprint.

Algorithm:
1. For each new article, compare title+summary against recent articles (last 72h)
2. Use fuzzy string matching (SequenceMatcher or similar)
3. Classify:
   - similarity >= 0.95 → "reprint" (copy-paste)
   - similarity >= 0.75 → "modified_reprint" (edited copy)
   - similarity < 0.75 → "original"
4. If reprint/modified, link to original_article_id (earliest matching article)

Similarity = weighted average:
- Title similarity: 40% weight
- Summary similarity: 60% weight
"""

from difflib import SequenceMatcher
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import Article

REPRINT_THRESHOLD = 0.95    # Almost identical = przedruk
MODIFIED_THRESHOLD = 0.75   # Similar enough = przedruk ze zmianami
LOOKBACK_HOURS = 72         # Compare against last 3 days

def similarity(a: str, b: str) -> float:
    """Fuzzy string similarity (0.0 - 1.0)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def classify_article(article: Article, db: Session) -> dict:
    """Classify article as original/reprint/modified_reprint.
    
    Returns: {"type": str, "original_id": int|None, "score": float}
    """
    cutoff = datetime.utcnow() - timedelta(hours=LOOKBACK_HOURS)
    
    # Get recent articles (exclude self)
    recent = (
        db.query(Article)
        .filter(
            Article.id != article.id,
            Article.fetched_at >= cutoff,
            Article.fetched_at < article.fetched_at,  # Only earlier articles
        )
        .order_by(Article.fetched_at.asc())
        .limit(500)  # Cap for performance
        .all()
    )
    
    best_score = 0.0
    best_match_id = None
    
    for other in recent:
        title_sim = similarity(article.title, other.title)
        
        # Quick filter: if titles are very different, skip full comparison
        if title_sim < 0.5:
            continue
        
        summary_sim = similarity(article.summary or "", other.summary or "")
        combined = title_sim * 0.4 + summary_sim * 0.6
        
        if combined > best_score:
            best_score = combined
            best_match_id = other.id
    
    if best_score >= REPRINT_THRESHOLD:
        return {"type": "reprint", "original_id": best_match_id, "score": best_score}
    elif best_score >= MODIFIED_THRESHOLD:
        return {"type": "modified_reprint", "original_id": best_match_id, "score": best_score}
    else:
        return {"type": "original", "original_id": None, "score": best_score}
```

### Krok 3: Integracja z AI enrichment job

W `src/scheduler.py`, w funkcji `_ai_enrich_job()`, po przetworzeniu AI,
dodaj wywołanie reprint detector:

```python
from .reprint_detector import classify_article

# After AI enrichment, classify reprint type
result = classify_article(article, db)
article.reprint_type = result["type"]
article.original_article_id = result["original_id"]
article.similarity_score = result["score"]
```

### Krok 4: Migracja bazy danych

Na VPS:
```sql
ALTER TABLE articles ADD COLUMN reprint_type VARCHAR(20);
ALTER TABLE articles ADD COLUMN original_article_id INTEGER REFERENCES articles(id);
ALTER TABLE articles ADD COLUMN similarity_score FLOAT;
```

## Kryteria gotowości
- [ ] Pola `reprint_type`, `original_article_id`, `similarity_score` dodane do modelu
- [ ] `src/reprint_detector.py` utworzony i zaimportowany
- [ ] Integracja z `_ai_enrich_job` w `scheduler.py`
- [ ] Migracja SQL na VPS
- [ ] Test: 2+ artykuły z tym samym tytułem → jeden "original", reszta "reprint"
- [ ] Deploy na VPS (docker compose build + up)

## Uwagi
- **NIE ruszaj** `src/dedup.py` — to osobny moduł do deduplikacji (zapobiega duplikatom)
- **NIE zmieniaj** logiki AI enrichment (Bielik prompt, parsing) — tylko dodaj AFTER AI processing
- **NIE ruszaj** schedulera poza dodaniem 3 linii w `_ai_enrich_job`
- `SequenceMatcher` z `difflib` jest w stdlib — nie wymaga nowych zależności
- Performance: limit 500 artykułów do porównania, title pre-filter 0.5 = szybkie
