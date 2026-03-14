# Knowledge Base — [crawl-dev 01]

> Przeczytaj NA STARCIE sesji. Dopisuj NA KOŃCU.

## Architektura
- Python 3.11, Flask admin panel
- Pipeline: fetch → parse → deduplicate → store (SQLite)
- Deploy: Docker na VPS 147.224.162.100
- Admin: port 5001 (`/admin/dashboard`)
- Cron: co 15 min fetch cycle

## Sesje pracy

### 2026-03-14 — Task 4.1: Feed Aggregate Children
- **Commit:** `9b830dc` → main (pushed)
- **Niedziela (agregat):** 19/21 diecezji children added (zamosclubaczow + wloclawek = dead DNS)
- **Onet:** aggregate + 4 children (kobieta, wiadomosci, kultura, przegladsportowy)
- **Interia:** aggregate + 7 children (biznes, kobieta, sport, swiatseriali, taniomam, wydarzenia, zielona)
- **Nowe standalone:** CIRE.pl (`/rss/kraj-swiat.xml`), Infor.pl (`/rss/wszystkie.xml`)
- **Brak RSS:** wyborcza.pl, se.pl, medonet.pl, tokfm.pl, polskieradio24.pl, radiozet.pl, eska.pl, stooq.pl
- **Subdomeny nie istnieją:** rp.pl, gazetaprawna.pl, pap.pl (używają ścieżek URL, nie subdomen)
- **Weryfikacja:** 556 sources loaded, 3 aggregates, 30 children total
- **Heartbeat → done**

### 2026-03-14 — Diagnoza YAML vs DB + polskie źródła
- **Problem:** YAML=556, DB=1687 (rozbieżność ~1131 feedów)
- **Root cause:** DB ma 6 ścieżek importu, YAML to tylko jedna z nich
- **Ścieżki do DB:** seed_db (YAML), polish_feeds.py (329 PL), google_news.py (~120+), opml_import.py, source_scout.py (auto), admin UI
- **Rekomendacja:** DB = source-of-truth, YAML = jeden z importerów
- **Brak language:pl:** polish_feeds.py NIE ustawia language='pl' przy imporcie → fix potrzebny
- **Brakujące PL portale:** ~27 top portali (TVP Info, TVN24, RMF24, Polsat News, Money.pl, WP.pl, Forbes PL, Business Insider PL, Spider's Web, AntyWeb itp.)
- **API do feedów:** GET /api/feeds → JSON z wszystkimi feedami
- **Raport:** feed_diagnosis_report.md
- **Heartbeat → done**

### 2026-03-14 — IMM Cross-Check + ARTMedia Client
- **Commit:** `a287618` → main (pushed)
- **IMM Excel:** 9228 clippings, 1221 portali, 1 katalog (WPiA UW), 831 fraz
- **Cross-check:** 1025 portali brakujących vs nasze feedy
- **Dodano:** 18 feedów do polish_feeds.py (TVN24, Polsat News, RMF24, Spider's Web, Salon24, DoRzeczy, itp.)
- **Fix:** language='pl' dodane do import_polish_feeds() (poprzednio brak)
- **ARTMedia:** seed_artmedia.py → ClientAccount(artmedia, tier=pro) + Project(wpia-uw, 11 keywords)
- **Uruchomienie na VPS:** wymaga `python scripts/seed_artmedia.py` + `python -m src.polish_feeds`
- **Deploy VPS:** git pull ✅, docker rebuild ✅, polish_feeds +13 new ✅, seed_artmedia (client=2, project=6) ✅
- **Uwaga:** `scripts/` NIE jest w Dockerfile COPY — trzeba docker cp do kontenera
- **Heartbeat → done**
