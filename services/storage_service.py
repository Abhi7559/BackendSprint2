import asyncio
import io
import logging
from typing import BinaryIO, Optional, Union
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError

from core.config import settings
from exceptions.domain import StorageFileNotFoundError, StorageOperationError

logger = logging.getLogger(__name__)


class StorageService:
    """
    Dedicated S3 storage service using boto3.
    
    Responsibilities:
    - Encapsulate all AWS S3 client interactions.
    - Connect to AWS S3 or local Floci simulator.
    - Ensure all blocking I/O and stream reads run inside asyncio.to_thread
      so the FastAPI async event loop is never blocked.
    - Handle domain exceptions for missing objects and S3 errors.
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ) -> None:
        self.bucket_name = bucket_name or settings.S3_BUCKET_NAME
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self.region_name = region_name or settings.S3_REGION
        self.aws_access_key_id = aws_access_key_id or settings.AWS_ACCESS_KEY_ID
        self.aws_secret_access_key = aws_secret_access_key or settings.AWS_SECRET_ACCESS_KEY

        # Configure boto3 client with path-style addressing for local Floci compatibility
        boto_config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
        )

        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            config=boto_config,
        )

    # ------------------------------------------------------------------
    # Synchronous Worker Methods (invoked via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _sync_upload(
        self,
        file_obj: Union[BinaryIO, bytes],
        key: str,
        content_type: Optional[str] = None,
    ) -> dict:
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        if isinstance(file_obj, bytes):
            buffer = io.BytesIO(file_obj)
        else:
            buffer = file_obj

        try:
            self._client.upload_fileobj(
                Fileobj=buffer,
                Bucket=self.bucket_name,
                Key=key,
                ExtraArgs=extra_args if extra_args else None,
            )
            return {
                "bucket": self.bucket_name,
                "key": key,
                "url": f"{self.endpoint_url}/{self.bucket_name}/{key}",
            }
        except (ClientError, BotoCoreError) as e:
            logger.error("Failed to upload file to S3: %s", e)
            raise StorageOperationError(f"Upload failed for key '{key}': {e}", original_error=e)

    def _sync_get(self, key: str) -> dict:
        try:
            response = self._client.get_object(Bucket=self.bucket_name, Key=key)
            body_bytes = response["Body"].read()
            return {
                "key": key,
                "content_type": response.get("ContentType", "application/octet-stream"),
                "content_length": response.get("ContentLength", len(body_bytes)),
                "content": body_bytes,
                "metadata": response.get("Metadata", {}),
            }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "404"):
                raise StorageFileNotFoundError(key=key, bucket=self.bucket_name)
            logger.error("Failed to retrieve file from S3: %s", e)
            raise StorageOperationError(f"Download failed for key '{key}': {e}", original_error=e)
        except BotoCoreError as e:
            logger.error("BotoCore error retrieving file from S3: %s", e)
            raise StorageOperationError(f"Download failed for key '{key}': {e}", original_error=e)

    def _sync_list(self, prefix: str = "", max_keys: int = 100) -> list[dict]:
        try:
            response = self._client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys,
            )
            contents = response.get("Contents", [])
            return [
                {
                    "key": item["Key"],
                    "size": item["Size"],
                    "last_modified": item["LastModified"].isoformat(),
                    "etag": item.get("ETag", "").strip('"'),
                }
                for item in contents
            ]
        except (ClientError, BotoCoreError) as e:
            logger.error("Failed to list objects in S3: %s", e)
            raise StorageOperationError(f"List failed for prefix '{prefix}': {e}", original_error=e)

    def _sync_delete(self, key: str) -> bool:
        try:
            self._client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except (ClientError, BotoCoreError) as e:
            logger.error("Failed to delete object from S3: %s", e)
            raise StorageOperationError(f"Delete failed for key '{key}': {e}", original_error=e)

    # ------------------------------------------------------------------
    # Asynchronous Public Interface (Async-Safe)
    # ------------------------------------------------------------------

    async def upload_file(
        self,
        file_obj: Union[BinaryIO, bytes],
        key: str,
        content_type: Optional[str] = None,
    ) -> dict:
        """Upload a file or bytes to S3 asynchronously."""
        return await asyncio.to_thread(self._sync_upload, file_obj, key, content_type)

    async def get_file(self, key: str) -> dict:
        """Retrieve a file and read its content from S3 asynchronously."""
        return await asyncio.to_thread(self._sync_get, key)

    async def list_files(self, prefix: str = "", max_keys: int = 100) -> list[dict]:
        """List files in the S3 bucket asynchronously."""
        return await asyncio.to_thread(self._sync_list, prefix, max_keys)

    async def delete_file(self, key: str) -> bool:
        """Delete a file from S3 asynchronously."""
        return await asyncio.to_thread(self._sync_delete, key)


# Singleton instance for dependency injection
storage_service = StorageService()
