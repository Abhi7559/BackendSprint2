import asyncio
import json
import logging
from typing import Optional
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from core.config import settings
from schemas.events import ReviewEvent
from services.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


class SQSEventPublisher(EventPublisher):
    """
    SQS implementation of EventPublisher using boto3.
    
    Responsibilities:
    - Encapsulate all SQS interactions and boto3 client access.
    - Synchronous boto3 send_message calls are offloaded to asyncio.to_thread
      so the event loop is never blocked.
    - Safely handles all connection and serialization errors without crashing.
    """

    def __init__(
        self,
        queue_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ) -> None:
        self.queue_name = queue_name or settings.SQS_QUEUE_NAME
        self.endpoint_url = endpoint_url or settings.SQS_ENDPOINT_URL
        self.region_name = region_name or settings.S3_REGION
        self.aws_access_key_id = aws_access_key_id or settings.AWS_ACCESS_KEY_ID
        self.aws_secret_access_key = aws_secret_access_key or settings.AWS_SECRET_ACCESS_KEY

        self._queue_url: Optional[str] = settings.SQS_QUEUE_URL

        boto_config = Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        )

        self._client = boto3.client(
            "sqs",
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            config=boto_config,
        )

    def _resolve_queue_url(self) -> Optional[str]:
        """Resolve queue URL from queue name if not already cached."""
        if self._queue_url:
            return self._queue_url

        try:
            response = self._client.get_queue_url(QueueName=self.queue_name)
            url = response.get("QueueUrl")
            # If Floci returned http://floci:4566 but we are calling from host (localhost), adjust hostname
            if url and "floci:4566" in url and "localhost" in self.endpoint_url:
                url = url.replace("floci:4566", "localhost:4566")
            self._queue_url = url
            return self._queue_url
        except (ClientError, BotoCoreError) as e:
            logger.warning("Could not resolve SQS queue URL for '%s': %s", self.queue_name, e)
            return None

    def check_health(self) -> bool:
        """Startup health check for SQS queue reachability."""
        try:
            url = self._resolve_queue_url()
            if url:
                logger.info("SQS queue '%s' reachable at %s", self.queue_name, url)
                return True
            logger.warning("SQS queue '%s' is not currently reachable.", self.queue_name)
            return False
        except Exception as e:
            logger.warning("SQS queue check failed during startup: %s", e)
            return False

    def _sync_send(self, payload_json: str, event_type: str, resource_id: str) -> bool:
        """Synchronous boto3 send_message executed in worker thread."""
        try:
            queue_url = self._resolve_queue_url()
            if not queue_url:
                logger.error(
                    "Cannot publish event '%s' for resource '%s': Queue URL unavailable.",
                    event_type,
                    resource_id,
                )
                return False

            self._client.send_message(
                QueueUrl=queue_url,
                MessageBody=payload_json,
                MessageAttributes={
                    "EventType": {
                        "DataType": "String",
                        "StringValue": event_type,
                    }
                },
            )
            logger.info("Published event '%s' for resource '%s' to SQS.", event_type, resource_id)
            return True
        except Exception as e:
            logger.exception(
                "Failed to publish event '%s' for resource '%s' to SQS: %s",
                event_type,
                resource_id,
                e,
            )
            return False

    async def publish(self, event: ReviewEvent) -> bool:
        """
        Publish ReviewEvent asynchronously to SQS without blocking the event loop.
        Safely serializes and logs errors.
        """
        try:
            payload_json = event.model_dump_json()
        except Exception as e:
            logger.exception("Failed to serialize event '%s': %s", event.event_type, e)
            return False

        return await asyncio.to_thread(
            self._sync_send,
            payload_json,
            event.event_type,
            str(event.resource_id),
        )


# Singleton instance for dependency injection
sqs_publisher = SQSEventPublisher()
