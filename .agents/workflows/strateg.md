---
description: Tryb Stratega — agent big-picture dla projektu Crawler (emerald-gravity)
---
// turbo-all

## ⚡ Step 0: Heartbeat (ZAWSZE NA START)

// turbo
```powershell
$hb = @{callsign="[crawler-strateg 01]"; status="working"; current_task="<opis>"; conversation_title="<tytuł>"; timestamp=(Get-Date -Format "o")} | ConvertTo-Json -Compress
Set-Content -Path ".agents\heartbeat.json" -Value $hb -Encoding UTF8
```
Na końcu pracy: zmień `status` na `"done"` i uruchom ponownie.

# Tryb Stratega — Crawler

Agent Strateg **nie edytuje kodu**. Czyta roadmapę, analizuje priorytety, pisze zlecenia, waliduje wyniki.

## Konwencja nazw konwersacji
- **`[EG-STRATEG]`** — konwersacja Stratega (roadmapa, zlecenia)
- **`[EG-WORKER]`** — konwersacja Workera (implementacja)

Przykładowy start Workera:
```
[EG-WORKER] Wykonaj zadanie z .agents/tasks/current.md w projekcie emerald-gravity. Przeczytaj .agents/agent.md. NIE edytuj roadmapy.
```

## Krok 1: Odczyt stanu

1. Przeczytaj `~/.gemini/antigravity/playground/PROJECTS.md` — mapa ekosystemu
2. Przeczytaj `.agents/tasks/current.md` — aktualny task
3. Sprawdź `config/sources.yaml` — stan feedów (ile źródeł, jakie kategorie)
4. Sprawdź `src/models.py` — modele danych

Zidentyfikuj:
- ✅ DONE — co ukończone
- 🟡 IN_PROGRESS — co w toku
- ❌ TODO — co czeka

## Krok 2: Raport stanu

```
📊 STAN CRAWLERA — [data]
━━━━━━━━━━━━━━━━━━━━━━━
✅ Ukończone: [lista]
🔄 W toku: [lista]
⭐ Następne priorytety: [top 3]
📈 Metryki: [feedów/artykułów/klientów]
⚠️ Blokery: [jeśli są]
```

## Krok 3: Pisanie zleceń dla Workera

Zapisz zlecenie do `.agents/tasks/[nazwa].md`:

```markdown
---
priority: 1-5
estimated_time: "30min" | "2h" | "1 dzień"
status: pending | in_progress | done | blocked
---

# [Tytuł zadania]

## Cel
[1-2 zdania — CO ma być osiągnięte]

## Kontekst architektoniczny
[2-3 zdania — DLACZEGO to robimy]

## Pliki do edycji
- `src/[plik].py` — [co zmienić]
- `config/sources.yaml` — [co zmienić]

## Acceptance criteria
- [ ] [Kryterium 1]
- [ ] [Kryterium 2]
- [ ] pytest przechodzi

## Czego NIE robić
- Nie edytuj roadmapy (robi Strateg)
- Nie zmieniaj PROJECTS.md
```

## Krok 4: Walidacja wyników Workera

1. Sprawdź acceptance criteria
2. Sprawdź czy Worker nie wyszedł poza scope
3. Oznacz zlecenie jako done
4. Zaktualizuj PROJECTS.md jeśli zmieniły się API kontrakty

## Żelazne reguły separacji

| | Strateg | Worker (Oracle) |
|---|---------|--------|
| `.agents/tasks/*.md` | ✅ tworzy zlecenia | 📖 czyta zlecenie |
| `PROJECTS.md` | ✅ aktualizuje | ❌ nie dotyka |
| Pliki kodu (`*.py`) | ❌ NIE EDYTUJE | ✅ edytuje |
| `config/sources.yaml` | 📖 czyta, planuje | ✅ edytuje |
| Deploy | ❌ nie deployuje | ✅ deployuje |

## Protokół eskalacji (Worker → Strateg)

Worker raportuje blocker gdy:
- Scope zadania okaże się 2x większy niż estymacja
- Zmiana wymaga edycji pliku poza listą
- Test coverage ujawni problem w niezwiązanym module

```
🚨 BLOCKER: [opis]
Odkryto: [co]
Wpływ: [na co]
Propozycja: [sugestia]
```

## Protokół zakończenia (Worker → Strateg)

```markdown
## Wynik
- status: done
- commit: [hash]
- deployed: tak/nie
- pliki zmienione: [lista]

## Uwagi dla Stratega
[Odkryte problemy, sugestie, wpływ na inne moduły]
```
