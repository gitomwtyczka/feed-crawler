# Dispatch: Deploy monitora prawy-archiver — emerald-gravity

**Do:** `[crawler-dev 01]`
**Workspace:** emerald-gravity
**Priorytet:** 🟡 P1 — widoczność operacyjna projektu prawy
**Od:** `[Supervisor 01 | sonic-void]`
**Data:** 2026-04-08

---

## ⚡ KROK 0 — zanim cokolwiek zrobisz

Przeczytaj blok systemowy — zawiera wszystkie parametry środowiskowe (GitHub MCP, FILE BRIDGE, targety VPS, raportowanie):
```
mcp_github_get_file_contents:
  owner: gitomwtyczka / repo: sonic-void / branch: master
  path: .agents/protocols/dispatch-system-block.md
```

Heartbeat przez GitHub MCP:
```json
{
  "callsign": "crawler-dev 01",
  "status": "working",
  "current_task": "deploy-prawy-monitor",
  "timestamp": "<ISO teraz>"
}
```
```
mcp_github_create_or_update_file → feed-crawler/main → .agents/heartbeat.json
```

📌 **Sugerowany model:** implementacyjny — dobry do kodu i deploy

---

## KONTEKST — dane zebrane przez Supervisora

VPS verify wykonany (08.04.2026 21:47). Dane potwierdzone live:

**Kontener prawy-archiver na oracle-crimson:**
```
prawy-archiver-prawy-archiver-run-af2813c72bb9   Up 8 hours
```
> Nazwa ma dynamiczny hash suffix. Użyj do docker exec:
> ```bash
> docker ps --filter name=prawy --format '{{.Names}}'
> ```

**prawy.db — live stats:**
```
articles: 14,931 total
  done:    31
  pending: 14,900
  error:   0
  images:  0/31  ← kolumna istnieje (format: images: X/Y)
```

**Ścieżka DB:**
- W kontenerze: `/app/data/prawy.db`
- Na hoście: `/home/ubuntu/prawy-archiver/data/prawy.db`

**Schema tabeli articles (potwierdzona):**
```
title, author, category, content_html, featured_image_url, status
status values: 'done' | 'pending' | 'error' | 'failed'
```

**Decyzja architektoniczna Supervisora:**
Panel monitoringu pokazuje: `total/done/pending/error` + opcjonalnie `images_ready` (ile artykułów ma featured_image_url != null).

---

## ZADANIA

### Zadanie 1 — Recon aktualnego stanu kodu

Sprawdź przez GitHub MCP co zostało zbudowane w poprzedniej sesji:
```
mcp_github_get_file_contents → feed-crawler/main → src/ (listuj)
mcp_github_get_file_contents → feed-crawler/main → templates/ (listuj)
```

Znajdź:
- Czy endpoint `/api/prawy/stats` już istnieje w kodzie?
- Czy frontend zakładka "Projekty" jest w templates?
- Czy raport poprzedniej sesji opisuje stan implementacji?

```
mcp_github_get_file_contents → feed-crawler/main → .agents/reports/ (listuj)
```

Zaraportuj co jest gotowe, co jeszcze nie.

### Zadanie 2 — Weryfikacja prawy.db dostępności z aplikacji

Sprawdź przez FILE BRIDGE czy prawy.db jest dostępna z poziomu kontenera emerald-gravity:

```json
{
  "id": "crawler-dev-prawy-access-01",
  "agent": "crawler-dev 01",
  "tool": "run_recipe",
  "args": {
    "recipe": "oracle-docker-status",
    "target": "oracle-crimson"
  }
}
```

Następnie sprawdź czy emerald-gravity ma dostęp do pliku DB (może być przez volume mount lub przez SSH):
```json
{
  "id": "crawler-dev-prawy-access-02",
  "agent": "crawler-dev 01",
  "tool": "execute_command",
  "args": {
    "target": "vultr-llm",
    "command": "ls -la /home/ubuntu/feed-crawler/ | head -20",
    "timeout": 15
  }
}
```

Jeśli DB nie jest dostępna bezpośrednio z emerald-gravity → zaraportuj do Supervisora z propozycją (periodic sync, proxy API, itp.) — NIE improwizuj rozwiązania.

### Zadanie 3 — Implementacja (jeśli kod jeszcze nie istnieje)

Na podstawie recon:

**Backend — endpoint `/api/prawy/stats`:**
- Pobiera dane z prawy.db (przez docker exec lub lokalnie jeśli mounted)
- Cache: odśwież max co 60s (nie uderzaj w DB przy każdym request)
- Format odpowiedzi:
```json
{
  "total_discovered": 0,
  "total_crawled": 0,
  "total_pending": 0,
  "total_errors": 0,
  "images_ready": 0,
  "last_updated": "ISO timestamp"
}
```
- Auth: tylko zalogowani adminowie

**Frontend — zakładka "Projekty" (admin-only):**
- Karta "prawy-archiver" z paskiem postępu `done / 136,000`
- Liczniki crawled / pending / errors
- Status: 🟢 działa / 🟡 pauza / 🔴 błąd (na podstawie czy pending > 0)
- Przycisk "Odśwież"

### Zadanie 4 — Deploy na VPS

Po implementacji:

```json
{
  "id": "crawler-dev-deploy-01",
  "agent": "crawler-dev 01",
  "tool": "run_recipe",
  "args": {
    "recipe": "deploy-full",
    "target": "oracle-crimson"
  }
}
```

Następnie zweryfikuj że panel `crawler.impresjapr.pl` działa i zakładka Projekty jest widoczna.

---

## WAŻNE ZASADY

- Zero cichych wyjątków — każdy błąd loguj.
- Jeśli prawy.db nie jest dostępna bezpośrednio → STOP i zaraportuj z propozycją.
- Jeśli architektura rozbieżna z oczekiwaniami → STOP i zaraportuj.

---

## RAPORTOWANIE — PODWÓJNE

### 1. Do stratega projektu (feed-crawler):
```
mcp_github_create_or_update_file:
  owner: gitomwtyczka / repo: feed-crawler / branch: main
  path: .agents/reports/2026-04-08_crawler-dev-01_prawy-monitor-deploy.md
  message: "report: [crawler-dev 01] prawy monitor deploy"
```

### 2. Kopia do Supervisora (sonic-void inbox):
```
mcp_github_create_or_update_file:
  owner: gitomwtyczka / repo: sonic-void / branch: master
  path: .agents/reports/inbox/2026-04-08_crawler-dev-01_prawy-monitor-deploy.md
  message: "report: [crawler-dev 01] prawy-monitor-deploy → supervisor inbox"
```

Raport zawiera:
- [ ] Recon — co było gotowe, co dobudowano
- [ ] Dostęp do prawy.db — jak rozwiązano
- [ ] Endpoint `/api/prawy/stats` — ścieżka, auth, cache
- [ ] Frontend — zakładka Projekty, plik/komponent
- [ ] Deploy — wynik, URL do weryfikacji

---

*[Supervisor 01 | sonic-void 08.04.2026 22:10] — dispatch wysłany*
