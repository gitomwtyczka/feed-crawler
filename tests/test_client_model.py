"""Tests for ClientAccount model."""
import pytest
from src.models import ClientAccount, Project
from src.auth import hash_password, verify_password


def test_client_account_creation(db):
    client = ClientAccount(
        username="testclient",
        password_hash=hash_password("pass123"),
        company_name="Test Corp",
        tier="basic",
        is_active=True,
    )
    db.add(client)
    db.commit()
    assert client.id is not None
    assert client.tier == "basic"


def test_client_project_relationship(db):
    client = ClientAccount(
        username="reltest",
        password_hash=hash_password("pass"),
        company_name="Rel Corp",
        is_active=True,
    )
    db.add(client)
    db.flush()

    project = Project(name="TestBrand", slug="testbrand", client_id=client.id, is_active=True)
    db.add(project)
    db.commit()

    assert len(client.projects) == 1
    assert client.projects[0].slug == "testbrand"


def test_client_password_verify():
    hashed = hash_password("secret")
    assert verify_password("secret", hashed)
    assert not verify_password("wrong", hashed)


def test_client_tiers(db):
    for tier in ["basic", "pro", "enterprise"]:
        client = ClientAccount(
            username=f"tier_{tier}",
            password_hash=hash_password("x"),
            company_name=f"Tier {tier}",
            tier=tier,
            is_active=True,
        )
        db.add(client)
    db.commit()
    tier_clients = db.query(ClientAccount).filter(ClientAccount.username.like("tier_%")).all()
    assert len(tier_clients) == 3
    assert {c.tier for c in tier_clients} == {"basic", "pro", "enterprise"}

