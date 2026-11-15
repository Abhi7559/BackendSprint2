import io
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from main import app
from dependencies.auth import get_current_user
from exceptions.domain import StorageFileNotFoundError, StorageOperationError
from services.storage_service import storage_service

# Mock authenticated user
mock_user = MagicMock()
mock_user.id = "00000000-0000-0000-0000-000000000001"
mock_user.username = "testcritic"
mock_user.role = "critic"

app.dependency_overrides[get_current_user] = lambda: mock_user
client = TestClient(app)


def test_upload_file_endpoint(monkeypatch):
    async def mock_upload(file_obj, key, content_type=None):
        return {
            "bucket": "film-review-assets-local",
            "key": key,
            "url": f"http://localhost:4566/film-review-assets-local/{key}",
        }

    monkeypatch.setattr(storage_service, "upload_file", mock_upload)

    file_content = b"Mock poster image binary content"
    files = {"file": ("poster.jpg", io.BytesIO(file_content), "image/jpeg")}

    response = client.post("/api/v1/storage/upload?folder=posters", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "poster.jpg"
    assert data["content_type"] == "image/jpeg"
    assert data["identifier"].startswith("posters/")
    assert data["bucket"] == "film-review-assets-local"


def test_get_file_endpoint_success(monkeypatch):
    async def mock_get(key):
        return {
            "key": key,
            "content_type": "text/plain",
            "content_length": 11,
            "content": b"Hello World",
            "metadata": {},
        }

    monkeypatch.setattr(storage_service, "get_file", mock_get)

    response = client.get("/api/v1/storage/files/reports/report.txt")
    assert response.status_code == 200
    assert response.content == b"Hello World"
    assert response.headers["content-type"].startswith("text/plain")


def test_get_file_endpoint_not_found(monkeypatch):
    async def mock_get_not_found(key):
        raise StorageFileNotFoundError(key=key, bucket="film-review-assets-local")

    monkeypatch.setattr(storage_service, "get_file", mock_get_not_found)

    response = client.get("/api/v1/storage/files/missing/poster.jpg")
    assert response.status_code == 404
    data = response.json()
    assert data["type"] == "StorageFileNotFoundError"
    assert "missing/poster.jpg" in data["message"]


def test_list_files_endpoint(monkeypatch):
    async def mock_list(prefix="", max_keys=50):
        return [
            {
                "key": "posters/poster1.png",
                "size": 5000,
                "last_modified": "2026-11-15T12:00:00+00:00",
                "etag": "etag1",
            }
        ]

    monkeypatch.setattr(storage_service, "list_files", mock_list)

    response = client.get("/api/v1/storage/files?prefix=posters/")
    assert response.status_code == 200
    data = response.json()
    assert data["prefix"] == "posters/"
    assert data["count"] == 1
    assert data["files"][0]["key"] == "posters/poster1.png"


def test_delete_file_endpoint(monkeypatch):
    async def mock_delete(key):
        return True

    monkeypatch.setattr(storage_service, "delete_file", mock_delete)

    response = client.delete("/api/v1/storage/files/posters/poster1.png")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"
    assert data["identifier"] == "posters/poster1.png"
