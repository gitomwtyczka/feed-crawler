"""Reclassify all feeds using updated source_tiers rules. Run: python -m src.reclassify_tiers"""
import sys; sys.path.insert(0, "/app")
from src.database import SessionLocal
from src.models import Feed
from src.source_tiers import classify_feed
from sqlalchemy import func

db = SessionLocal()
feeds = db.query(Feed).all()
changed = 0
for f in feeds:
    new_tier = classify_feed(f.rss_url or "", f.name or "")
    if f.source_tier != new_tier:
        print(f"  {f.name[:50]:50s}  T{f.source_tier} → T{new_tier}")
        f.source_tier = new_tier
        changed += 1
db.commit()
print(f"\nReclassified {changed}/{len(feeds)} feeds")
for tier, cnt in db.query(Feed.source_tier, func.count(Feed.id)).group_by(Feed.source_tier).order_by(Feed.source_tier).all():
    print(f"  T{tier}: {cnt}")
db.close()
