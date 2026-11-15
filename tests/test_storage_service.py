import io
import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

from exceptions.domain import StorageFileNotFoundError, StorageOperationError
from services.storage_service import StorageService


@pytest.fixture
def mock_storage_service():
    service = StorageService(
        bucket_name="test-bucket",
        endpoint_url="http://localhost:4566",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    # Mock underlying boto3 client
    service._client = MagicMock()
    return service


@pytest.mark.asyncio
async def test_upload_file_bytes(mock_storage_service):
    data = b"Hello S3"
    result = await mock_storage_service.upload_file(data, "posters/test.jpg", content_type="image/jpeg")

    assert result["bucket"] == "test-bucket"
    assert result["key"] == "posters/test.jpg"
    assert "url" in result
    mock_storage_service._client.upload_fileobj.assert_called_once()


@pytest.mark.asyncio
async def test_get_file_success(mock_storage_service):
    mock_body = MagicMock()
    mock_body.read.return_value = b"File Content"

    mock_storage_service._client.get_object.return_value = {
        "Body": mock_body,
        "ContentType": "text/plain",
        "ContentLength": 12,
        "Metadata": {"author": "test"},
    }

    result = await mock_storage_service.get_file("documents/doc.txt")
    assert result["key"] == "documents/doc.txt"
    assert result["content"] == b"File Content"
    assert result["content_type"] == "text/plain"
    assert result["content_length"] == 12


@pytest.mark.asyncio
async def test_get_file_not_found(mock_storage_service):
    error_response = {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}}
    mock_storage_service._client.get_object.side_effect = ClientError(error_response, "GetObject")

    with pytest.raises(StorageFileNotFoundError) as exc_info:
        await mock_storage_service.get_file("missing.jpg")

    assert "missing.jpg" in str(exc_info.value)
    assert "test-bucket" in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_files(mock_storage_service):
    from datetime import datetime, timezone

    mock_storage_service._client.list_objects_v2.return_value = {
        "Contents": [
            {
                "Key": "posters/film1.png",
                "Size": 1024,
                "LastModified": datetime(2026, 11, 15, 12, 0, 0, tzinfo=timezone.utc),
                "ETag": '"abcdef123456"',
            }
        ]
    }

    results = await mock_storage_service.list_files(prefix="posters/")
    assert len(results) == 1
    assert results[0]["key"] == "posters/film1.png"
    assert results[0]["size"] == 1024
    assert results[0]["etag"] == "abcdef123456"


@pytest.mark.asyncio
async def test_delete_file(mock_storage_service):
    mock_storage_service._client.delete_object.return_value = {}

    success = await mock_storage_service.delete_file("posters/film1.png")
    assert success is True
    mock_storage_service._client.delete_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="posters/film1.png",
    )


@pytest.mark.asyncio
async def test_storage_operation_error_on_client_error(mock_storage_service):
    error_response = {"Error": {"Code": "InternalError", "Message": "Something broke"}}
    mock_storage_service._client.upload_fileobj.side_effect = ClientError(error_response, "UploadFileObj")

    with pytest.raises(StorageOperationError) as exc_info:
        await mock_storage_service.upload_file(b"data", "fail.txt")

    assert "fail.txt" in str(exc_info.value)
