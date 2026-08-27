import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def app_env(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield SimpleNamespace(client=TestClient(app), engine=engine, Session=Session)
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


@pytest.fixture()
def client(app_env):
    return app_env.client


@pytest.fixture()
def producer(client):
    return client.post(
        "/api/participants", json={"name": "Dzongu Organic Co-op", "role": "producer"}
    ).json()


@pytest.fixture()
def handler(client):
    return client.post(
        "/api/participants", json={"name": "Gangtok Packhouse", "role": "handler"}
    ).json()


@pytest.fixture()
def batch(client, producer):
    return client.post(
        "/api/batches",
        json={
            "product_name": "Large Cardamom",
            "origin": "Dzongu, North Sikkim",
            "organic_claim": True,
            "producer_id": producer["id"],
            "harvest_note": "Harvested after monsoon",
        },
    ).json()
