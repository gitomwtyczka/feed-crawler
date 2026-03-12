---
feature_id: "3.1"
status: pending
assigned: worker
created: 2026-03-12
priority: high
depends_on: "2.0 (done)"
---

# Task 3.1: Model ClientAccount + migracja DB + seed

## Kontekst
Budujemy panel monitoringu dla klientów (agencji PR). To krok 1 z 3:
- **3.1** Model + DB (ten task) 
- 3.2 Routes + templates
- 3.3 AI Brief + dashboard

## Lokalizacja kodu
- Workspace: `c:\Users\tomas2\.gemini\antigravity\playground\emerald-gravity`
- Models: `src/models.py`
- Auth (referencja): `src/auth.py` — zobaczysz jak admini mają hash_password, verify_password
- Istniejący model Project: `src/models.py` — tabela `projects`

## Implementacja

### Krok 1: Model `ClientAccount` w `src/models.py`

Dodaj PO klasie `Project` (końcówka pliku):

```python
class ClientAccount(Base):
    """Client account for media monitoring panel."""
    __tablename__ = "client_accounts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    tier = Column(String(20), nullable=False, default="basic")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relacja do projektów
    projects = relationship("Project", back_populates="client")
```

### Krok 2: Modyfikuj `Project` — dodaj `client_id`

W istniejącej klasie `Project` dodaj:

```python
    client_id = Column(Integer, ForeignKey("client_accounts.id"), nullable=True)
    client = relationship("ClientAccount", back_populates="projects")
```

`nullable=True` bo istniejące projekty (Strabag, Orlen, PZU, TVP) nie mają jeszcze klienta.

### Krok 3: Migration script `scripts/migrate_client.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "--- Create client_accounts table ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
CREATE TABLE IF NOT EXISTS client_accounts (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    tier VARCHAR(20) NOT NULL DEFAULT 'basic',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);"

echo "--- Add client_id to projects ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "
ALTER TABLE projects ADD COLUMN IF NOT EXISTS client_id INTEGER REFERENCES client_accounts(id);"

echo "--- Verify ---"
docker exec crawler-db psql -U crawler -d feed_crawler -c "\d client_accounts"
docker exec crawler-db psql -U crawler -d feed_crawler -c "\d projects"
```

### Krok 4: Seed script `scripts/seed_client.py`

Uruchamiany wewnątrz kontenera Docker lub jako standalone:

```python
"""Seed test client account: diaverum."""
from src.auth import hash_password
from src.database import SessionLocal
from src.models import ClientAccount, Project

def seed():
    db = SessionLocal()
    try:
        # Check if already seeded
        existing = db.query(ClientAccount).filter(ClientAccount.username == "diaverum").first()
        if existing:
            print("Client 'diaverum' already exists, skipping")
            return
        
        # Create client
        client = ClientAccount(
            username="diaverum",
            password_hash=hash_password("test123"),
            company_name="Diaverum",
            email="monitoring@diaverum.pl",
            tier="pro",
            is_active=True,
        )
        db.add(client)
        db.flush()  # get id
        
        # Assign existing projects to this client
        for slug in ["strabag", "orlen", "pzu"]:
            project = db.query(Project).filter(Project.slug == slug).first()
            if project:
                project.client_id = client.id
                print(f"  Assigned project '{slug}' to diaverum")
        
        db.commit()
        print(f"Created client: diaverum (id={client.id}, tier=pro)")
        print(f"  Projects: strabag, orlen, pzu")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
```

### Krok 5: Testy `tests/test_client_model.py`

```python
"""Tests for ClientAccount model."""
import pytest
from src.models import ClientAccount, Project
from src.auth import hash_password, verify_password

def test_client_account_creation(db_session):
    client = ClientAccount(
        username="testclient",
        password_hash=hash_password("pass123"),
        company_name="Test Corp",
        tier="basic",
        is_active=True,
    )
    db_session.add(client)
    db_session.commit()
    assert client.id is not None
    assert client.tier == "basic"

def test_client_project_relationship(db_session):
    client = ClientAccount(
        username="reltest",
        password_hash=hash_password("pass"),
        company_name="Rel Corp",
        is_active=True,
    )
    db_session.add(client)
    db_session.flush()
    
    project = Project(name="TestBrand", slug="testbrand", client_id=client.id, is_active=True)
    db_session.add(project)
    db_session.commit()
    
    assert len(client.projects) == 1
    assert client.projects[0].slug == "testbrand"

def test_client_password_verify():
    hashed = hash_password("secret")
    assert verify_password("secret", hashed)
    assert not verify_password("wrong", hashed)

def test_client_tiers(db_session):
    for tier in ["basic", "pro", "enterprise"]:
        client = ClientAccount(
            username=f"tier_{tier}",
            password_hash=hash_password("x"),
            company_name=f"Tier {tier}",
            tier=tier,
            is_active=True,
        )
        db_session.add(client)
    db_session.commit()
    assert db_session.query(ClientAccount).count() == 3
```

## Kryteria gotowości
- [ ] Model `ClientAccount` w `models.py`
- [ ] `client_id` FK w `Project`
- [ ] Migration script `scripts/migrate_client.sh`
- [ ] Seed script `scripts/seed_client.py`
- [ ] Testy: ≥4 passed
- [ ] Commit + push

## Uwagi
- **NIE ruszaj** `web.py` — routes będą w tasku 3.2
- **NIE twórz** templates — to task 3.2
- Import `ClientAccount` z `models.py` — dodaj do `__all__` jeśli istnieje
- Hashing: użyj `hash_password` z `src/auth.py` (już jest `passlib`)
- `nullable=True` na `client_id` — istniejące projekty nie mają klienta
