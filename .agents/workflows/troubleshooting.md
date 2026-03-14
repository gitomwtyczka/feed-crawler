---
description: Znane problemy i sprawdzone rozwiązania — stosuj ZANIM zaczniesz metodę prób i błędów
---
// turbo-all

# Troubleshooting — rozwiązania powtarzalnych problemów

## 1. Git — Author identity unknown

**Problem**: `fatal: unable to auto-detect email address`
**Rozwiązanie**: Przed pierwszym commitem w nowym repo:
```powershell
git config user.email "supervisor@impresjaai.pl"
git config user.name "Supervisor 01"
```

## 2. Git — push wisi (credential helper GUI)

**Problem**: `git push` wisi bez komunikatu — czeka na GUI popup Credential Manager
**Rozwiązanie** (jednorazowe, globalne):
```powershell
git config --global credential.helper "!gh auth git-credential"
```
Używa `gh` CLI (już zalogowane) zamiast GUI credential managera.

**Problem**: Polskie znaki wyświetlają się jako `?` lub `???`
**Rozwiązanie**: Na początku skryptu/sesji:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
```

## 3. PowerShell — CRLF vs LF warnings w git

**Problem**: `warning: LF will be replaced by CRLF`
**Rozwiązanie**: Ignoruj (kosmetyczne) LUB ustaw globalnie:
```powershell
git config --global core.autocrlf true
```

## 4. PowerShell — ścieżki z spacjami

**Problem**: Polecenia z przestrzeniami w ścieżkach się psują
**Rozwiązanie**: Zawsze otaczaj cudzysłowami:
```powershell
cd "c:\Users\tomas2\.gemini\antigravity\playground\sonic-void"
```

## 5. Python HTTP server — port zajęty

**Problem**: `OSError: [Errno 10048] address already in use`
**Rozwiązanie**:
```powershell
netstat -ano | findstr :8080
taskkill /PID <pid> /F
```

## 6. SSH do VPS — timeout / permission denied

**Problem**: SSH wisi lub odmawia
**Rozwiązanie**:
```powershell
# Sprawdź klucz
ssh -i "$env:USERPROFILE\.ssh\oracle_vps" -o ConnectTimeout=5 ubuntu@147.224.162.100 "echo ok"
```

## 7. npm/npx — EACCES lub permission error

**Problem**: Node nie ma uprawnień
**Rozwiązanie**: Uruchom PowerShell jako Administrator lub:
```powershell
npm config set prefix "$env:APPDATA\npm"
```

## 8. grep/ripgrep — nie znajduje w plikach z BOM

**Problem**: `rg` nie widzi polskich znaków w plikach zapisanych z BOM
**Rozwiązanie**: Używaj `--encoding utf-8` lub szukaj po ASCII fragmentach tekstu

## Zasada

> **Gdy napotkasz nowy powtarzalny błąd:**
> 1. Zapisz go tutaj z rozwiązaniem
> 2. Zastosuj rozwiązanie we WSZYSTKICH projektach
> 3. Nie powtarzaj metody prób i błędów
