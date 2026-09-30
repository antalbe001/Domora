import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.dependencies import get_listing_repository
from app.main import create_app
from app.repositories.in_memory import InMemoryListingRepository
from app.settings import Settings, get_settings


def _export(*references: str) -> dict[str, Any]:
    return {
        "listings": [
            {
                "reference": reference,
                "transaction": "sale",
                "title": f"{reference} – Appartamento",
                "url": f"https://example.test/annunci/{reference.lower()}/",
                "features": {"posizione": "Via Roma 1 - PORDENONE"},
            }
            for reference in references
        ]
    }


def _client(
    tmp_path: Path, *, admin_token: str, references: tuple[str, ...] = ("V1", "V2")
) -> tuple[TestClient, InMemoryListingRepository]:
    path = tmp_path / "annunci.json"
    path.write_text(json.dumps(_export(*references)), encoding="utf-8")

    repository = InMemoryListingRepository([])
    app = create_app()
    app.dependency_overrides[get_listing_repository] = lambda: repository
    app.dependency_overrides[get_settings] = lambda: Settings(
        listings_path=path, admin_token=admin_token
    )
    return TestClient(app), repository


def test_reloads_the_catalogue_with_the_right_token(tmp_path: Path) -> None:
    client, repository = _client(tmp_path, admin_token="segreto")

    response = client.post(
        "/api/admin/reload", headers={"Authorization": "Bearer segreto"}
    )

    assert response.status_code == 200
    assert response.json()["loaded"] == 2
    assert repository.get_by_reference("V1") is not None


def test_refuses_a_wrong_token(tmp_path: Path) -> None:
    client, repository = _client(tmp_path, admin_token="segreto")

    response = client.post(
        "/api/admin/reload", headers={"Authorization": "Bearer sbagliato"}
    )

    assert response.status_code == 401
    assert repository.get_by_reference("V1") is None


def test_refuses_a_missing_token(tmp_path: Path) -> None:
    client, _ = _client(tmp_path, admin_token="segreto")

    assert client.post("/api/admin/reload").status_code == 401


def test_the_endpoint_is_closed_when_no_token_is_configured(tmp_path: Path) -> None:
    """An unset ADMIN_TOKEN must not mean "anyone may reload"."""
    client, _ = _client(tmp_path, admin_token="")

    response = client.post("/api/admin/reload", headers={"Authorization": "Bearer "})

    assert response.status_code == 403


def test_health_reports_how_many_listings_are_loaded(tmp_path: Path) -> None:
    client, repository = _client(tmp_path, admin_token="segreto")
    client.post("/api/admin/reload", headers={"Authorization": "Bearer segreto"})

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "listings": 2}
