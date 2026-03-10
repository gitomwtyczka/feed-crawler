# Feed Crawler

Oddzielny mikroserwis wspierający SaaS Editorial Assistant. Pobiera artykuły z feedów RSS/Atom i API, deduplikuje je, taguje działami tematycznymi i (opcjonalnie) dostarcza do głównej aplikacji SaaS przez REST webhook.

## Stack technologiczny

- **Python 3.12+** z async (aiohttp)
- **SQLAlchemy 2.0** — ORM (SQLite dev / PostgreSQL prod)
- **feedparser** — parsowanie RSS/Atom
- **APScheduler** — harmonogram pobierania
- **pytest** — testy automatyczne
- **ruff** — linting (identyczne reguły jak SaaS backend)
- **Discord** — powiadomienia o błędach i podsumowaniach

## Źródła

Aktualnie **27 feedów RSS** w **6 działach** (z pliku OPML):

| Dział | Feedów | Przykłady |
|---|---|---|
| DEFENCE & GEOPOLITICS | 5 | ISW, Atlantic Council, CSIS |
| ECONOMY & GLOBAL TRADE | 5 | IMF, ECB, OECD |
| SCIENCE & HIGH-TECH | 7 | Nature, NASA, MIT, CERN |
| HEALTH & BIOTECH | 4 | WHO, CDC, STAT News |
| ENERGY & CLIMATE | 3 | IEA, IRENA |
| CYBER & DIGITAL | 3 | Check Point, OpenAI |

## Quick Start

```bash
# 1. Virtual environment
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

# 2. Dependencies
pip install -r requirements.txt

# 3. Config
copy .env.example .env
# Edytuj .env (opcjonalnie: Discord webhook, SaaS webhook)

# 4. Uruchom jeden cykl pobierania
python -m src.scheduler

# 5. Testy
pytest tests/ -v

# 6. Lint
ruff check src/ tests/
```

## Struktura

```
feed-crawler/
├── src/
│   ├── models.py          # Feed, Department, Article, FetchLog (SQLAlchemy)
│   ├── database.py        # Engine + session management
│   ├── config_loader.py   # Import OPML + load YAML config
│   ├── feed_parser.py     # Async RSS/Atom fetching (aiohttp + feedparser)
│   ├── dedup.py           # SHA256 hash deduplication
│   ├── scheduler.py       # Fetch cycle orchestration
│   ├── webhook.py         # SaaS delivery (offline-first)
│   └── discord_notifier.py # Discord alerts (errors, summaries)
├── config/
│   ├── sources.yaml       # 27 feeds (auto-generated from OPML)
│   └── departments.yaml   # 6 departments + 2 future slots
├── tests/                 # pytest (conftest + 4 test suites)
├── data/source_opml/      # Archived OPML files
├── requirements.txt
├── ruff.toml
└── .env.example
```

## Tryby pracy

1. **Offline** (domyślny) — pobiera feedy → zapisuje do lokalnej DB. Bez webhooków.
2. **Online** — dodatkowo wysyła nowe artykuły do SaaS (`SAAS_WEBHOOK_URL` w .env).
3. **Scheduled** — APScheduler odpala cykle co N minut (per feed konfigurowalny interwał).

## Przyszłe działy

- `HISTORYCZNY` — publikacje historyczne
- `STATYSTYKI` — Eurostat, GUS i inne
