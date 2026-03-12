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
