---
feature_id: "4.1"
status: pending
assigned: worker
created: 2026-03-13
priority: high
depends_on: "aggregate feed system deployed"
---

# Task 4.1: Add Feed Aggregate Children (Subdomains)

## Context
We've deployed a **Smart Crawling system** with aggregate + child feed support:
- `feed_role: aggregate` = primary feed, fetched every 15 min
- `feed_role: child` = backup feed, audited every 6h
- Children are linked via `parent_feed_id` in the `Feed` model
- Dedup prevents duplicate articles from aggregate + child

**Your job**: Add child feeds for existing aggregates, and discover RSS for portals without standard RSS URLs.

## Workspace
- `c:\Users\tomas2\.gemini\antigravity\playground\emerald-gravity`
- Config: `config/sources.yaml`
- Model reference: `src/models.py` (see `Feed.feed_role`, `Feed.parent_feed_id`)

## Part 1: Children for Niedziela.pl (21 Diecezji)

Add under the existing `Niedziela (agregat)` entry in `sources.yaml`:

```yaml
- name: Niedziela (agregat)
  url: https://www.niedziela.pl
  rss_url: https://www.niedziela.pl/rss
  feed_type: rss
  feed_role: aggregate
  fetch_interval: 15
  language: pl
  departments:
    - konkurencja-ogolne-lifestyle
  children:
    - name: Niedziela Częstochowa
      rss_url: https://czestochowa.niedziela.pl/rss
      audit_interval: 360
    - name: Niedziela Kraków
      rss_url: https://krakow.niedziela.pl/rss
      audit_interval: 360
    # ... add ALL 21 diecezji from IMM list
```

IMM diecezje (find RSS for each):
bielsko, czestochowa, drohiczyn, kielce, krakow, legnica, lodz, lublin,
plus, przemysl, radom, rzeszow, sandomierz, siedlce, sosnowiec,
szczecin, tarnow, torun, warszawa, wlocdawek, zamosclubaczow

## Part 2: Children for Existing Portals

For these portals we **already have the main feed**. Add children with `feed_role: aggregate` on the parent and subdomain children:

### rp.pl (11 subdomains in IMM)
Subdomains: biznes.rp.pl, cyfrowa.rp.pl, edukacja.rp.pl, energia.rp.pl, 
gospodarka.rp.pl, historia.rp.pl, pieniadze.rp.pl, pro.rp.pl, archiwum.rp.pl

### onet.pl (6 subdomains)
Subdomains: kobieta.onet.pl, kultura.onet.pl, przegladsportowy.onet.pl, 
wiadomosci.onet.pl, zapytaj.onet.pl

### interia.pl (7 subdomains)
Subdomains: biznes.interia.pl, kobieta.interia.pl, sport.interia.pl, 
swiatseriali.interia.pl, taniomam.interia.pl, wydarzenia.interia.pl, zielona.interia.pl

### gazetaprawna.pl (7 subdomains)
Subdomains: biznes.gazetaprawna.pl, cyfrowa-gospodarka.gazetaprawna.pl, 
edgp.gazetaprawna.pl, kultura.gazetaprawna.pl, podatki.gazetaprawna.pl, 
serwisy.gazetaprawna.pl

### pap.pl (5 subdomains)
Subdomains: biznes.pap.pl, samorzad.pap.pl, wideo.pap.pl, zdrowie.pap.pl

### gazeta.pl (5 subdomains)
Subdomains: forum.gazeta.pl, kobieta.gazeta.pl, kultura.gazeta.pl, 
next.gazeta.pl, wiadomosci.gazeta.pl

## Part 3: Discover RSS for No-RSS Portals

These major portals had NO standard RSS. Try to:
1. Scrape their homepage for `<link rel="alternate" type="application/rss+xml">` tags
2. Try common RSS paths: `/rss`, `/feed`, `/feed.xml`, `/rss.xml`, `/atom.xml`
3. If no RSS found, skip them — they'll be covered by GNews

Portals to check:
- wyborcza.pl (95 articles in IMM!)
- se.pl (Super Express)
- medonet.pl
- tokfm.pl
- polskieradio24.pl
- radiozet.pl
- cire.pl
- stooq.pl
- eska.pl
- infor.pl

## Part 4: NaszeMiasto + Twoje-Miasto Subdomains

These platforms don't have standard RSS. Research whether individual subdomains like
`torun.naszemiasto.pl` have RSS feeds. If not, they'll be covered by GNews.

Try these subdomain patterns first:
- `https://torun.naszemiasto.pl/rss`
- `https://krakow.naszemiasto.pl/rss`
- `https://warszawa.naszemiasto.pl/rss`
- Same for twoje-miasto.pl

If RSS exists, create an aggregate group. If not, document findings.

## Acceptance Criteria
- [ ] Children added for Niedziela.pl (all 21 diecezji with RSS)
- [ ] At least 3 existing portals converted to aggregate + children
- [ ] RSS discovery attempted for all no-RSS portals
- [ ] `config/sources.yaml` updated with new entries
- [ ] Commit + push to main
- [ ] Document findings (which portals have RSS, which don't)

## Notes
- Use `feed_role: aggregate` on parent, `feed_role: child` on children
- Children inherit `departments` from parent
- `audit_interval: 360` (6h) is default for children
- YAML format: `children:` key under parent feed
- Don't modify `models.py` or `scheduler.py` — they're already ready
- Run `python -c "from src.config_loader import load_sources; s = load_sources(); print(f'{len(s)} sources loaded')"` to verify YAML syntax
