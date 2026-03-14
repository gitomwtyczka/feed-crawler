---
description: Worker workflow — jak wykonywać taski jako [crawler-oracle 01]
---
// turbo-all

## ⚡ Step 0: Heartbeat (ZAWSZE NA START)

// turbo
```powershell
$hb = @{callsign="[crawler-oracle 01]"; status="working"; current_task="<opis>"; conversation_title="<tytuł>"; timestamp=(Get-Date -Format "o")} | ConvertTo-Json -Compress
Set-Content -Path ".agents\heartbeat.json" -Value $hb -Encoding UTF8
```
Na końcu pracy: zmień `status` na `done` i uruchom ponownie.

# Worker Workflow — Crawler (emerald-gravity)

## Uruchamianie

User mówi jedno z:
- `/worker` lub `[EG-WORKER]`
- „wykonaj task" / „zrób current.md"
- Bezpośrednie zlecenie

## Krok 1: Odczyt zlecenia

```
cat c:\Users\tomas2\.gemini\antigravity\playground\emerald-gravity\.agents\tasks\current.md
```

Przeczytaj zlecenie, zidentyfikuj:
- **Cel** — co ma być osiągnięte
- **Pliki do edycji** — lista z zlecenia
- **Acceptance criteria** — lista checkboxów
- **Czego NIE robić** — ograniczenia

## Krok 2: Weryfikacja środowiska

```
cd c:\Users\tomas2\.gemini\antigravity\playground\emerald-gravity && python -c "from src.config_loader import load_sources; print('OK')"
```

## Krok 3: Implementacja

Edytuj wyłącznie pliki wymienione w zleceniu. Po każdej znaczącej zmianie:

```
cd c:\Users\tomas2\.gemini\antigravity\playground\emerald-gravity && python -m pytest tests/ -x -q 2>&1 | tail -20
```

## Krok 4: Commit + Push

```
cd c:\Users\tomas2\.gemini\antigravity\playground\emerald-gravity && git add -A
```

```
cd c:\Users\tomas2\.gemini\antigravity\playground\emerald-gravity && git commit -m "<TYPE>: <DESCRIPTION>"
```
Types: `feat:`, `fix:`, `chore:`, `task:`

```
cd c:\Users\tomas2\.gemini\antigravity\playground\emerald-gravity && git push origin main
```

## Krok 5: Deploy

```
ssh -i "$env:USERPROFILE\.ssh\oracle-crimson.key" ubuntu@147.224.162.100 "cd /home/ubuntu/emerald-gravity && git pull && sudo docker compose up -d --build 2>&1 | tail -15"
```

```
ssh -i "$env:USERPROFILE\.ssh\oracle-crimson.key" ubuntu@147.224.162.100 "sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -i crawler"
```

## Krok 6: Raport

Dopisz do pliku zlecenia sekcję wyników:

```markdown
## Wynik
- status: done
- commit: [hash]
- deployed: tak/nie
- pliki zmienione: [lista]

## Uwagi dla Stratega
[Odkryte problemy, sugestie]
```

## SafeToAutoRun — zasady

Komendy **bezpieczne** (SafeToAutoRun: true):
- `cat`, `ls`, `find`, `grep`, `head`, `tail`
- `python -c "import ..."` (weryfikacja importów)
- `python -m pytest` (testy)
- `git status`, `git log`, `git diff`
- `docker ps`, `docker logs`

Komendy **wymagające zgody** (SafeToAutoRun: false):
- `git push` (nieodwracalne)
- `rm`, `del`, `Remove-Item` (destrukcyjne)
- `docker restart`, `docker compose up --build` (deploy)
- `ssh` + komendy modyfikujące (deploy na serwer)
- Wszystko z `sudo`
