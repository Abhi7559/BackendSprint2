import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from main import app
from dependencies.auth import get_current_user
from dependencies.database import get_db
from dependencies.events import get_event_publisher
from schemas.events import ReviewEvent
from services.event_publisher import EventPublisher
from services.sqs_publisher import SQSEventPublisher


# ---------------------------------------------------------------------------
# Unit tests for ReviewEvent Schema
# ---------------------------------------------------------------------------

def test_review_event_schema_creation():
    """Verifies ReviewEvent contains only event_type, resource_id, and timezone-aware UTC timestamp."""
    event = ReviewEvent(
        event_type="review.created",
        resource_id=101,
    )
    assert event.event_type == "review.created"
    assert event.resource_id == 101
    assert event.timestamp.tzinfo is not None
    assert event.timestamp.tzinfo == timezone.utc

    # Verify serialized payload does NOT contain full review fields
    payload = json.loads(event.model_dump_json())
    assert set(payload.keys()) == {"event_type", "resource_id", "timestamp"}
    assert payload["event_type"] == "review.created"
    assert payload["resource_id"] == 101


def test_review_event_with_uuid():
    """Verifies ReviewEvent works with UUID resource IDs."""
    review_uuid = str(uuid.uuid4())
    event = ReviewEvent(
        event_type="review.updated",
        resource_id=review_uuid,
    )
    assert event.event_type == "review.updated"
    assert event.resource_id == review_uuid


# ---------------------------------------------------------------------------
# Unit tests for SQSEventPublisher
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqs_publisher_successful_publish():
    """Publisher successfully serializes and sends message via boto3 SQS client."""
    publisher = SQSEventPublisher(
        queue_name="test-queue",
        endpoint_url="http://localhost:4566",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    publisher._client = MagicMock()
    publisher._client.get_queue_url.return_value = {"QueueUrl": "http://localhost:4566/000000000000/test-queue"}
    publisher._client.send_message.return_value = {"MessageId": "msg-12345"}

    event = ReviewEvent(event_type="review.created", resource_id="rev-101")
    success = await publisher.publish(event)

    assert success is True
    publisher._client.send_message.assert_called_once()
    call_args = publisher._client.send_message.call_args[1]
    assert call_args["QueueUrl"] == "http://localhost:4566/000000000000/test-queue"
    assert "review.created" in call_args["MessageBody"]
    assert "rev-101" in call_args["MessageBody"]


@pytest.mark.asyncio
async def test_sqs_publisher_handles_client_error():
    """Publisher failure is captured, logged, and returns False without crashing."""
    publisher = SQSEventPublisher(queue_name="test-queue")
    publisher._client = MagicMock()
    publisher._client.get_queue_url.return_value = {"QueueUrl": "http://localhost:4566/000000000000/test-queue"}
    publisher._client.send_message.side_effect = ClientError(
        {"Error": {"Code": "QueueDoesNotExist", "Message": "Queue not found"}},
        "SendMessage",
    )

    event = ReviewEvent(event_type="review.updated", resource_id="rev-101")
    success = await publisher.publish(event)
    assert success is False


def test_sqs_publisher_startup_health_check_failure_does_not_crash():
    """Queue unavailable during startup logs a warning and returns False without raising."""
    publisher = SQSEventPublisher(queue_name="nonexistent-queue")
    publisher._client = MagicMock()
    publisher._client.get_queue_url.side_effect = ClientError(
        {"Error": {"Code": "QueueDoesNotExist", "Message": "Queue not found"}},
        "GetQueueUrl",
    )

    is_healthy = publisher.check_health()
    assert is_healthy is False


# ---------------------------------------------------------------------------
# Unit tests for Route-Level Event Publishing with BackgroundTasks
# ---------------------------------------------------------------------------

class MockEventPublisher(EventPublisher):
    def __init__(self):
        self.published_events = []

    async def publish(self, event: ReviewEvent) -> bool:
        self.published_events.append(event)
        return True

    def check_health(self) -> bool:
        return True


@pytest.fixture
def mock_publisher():
    return MockEventPublisher()


@pytest.fixture
def authenticated_client(mock_publisher):
    # Mock current user as critic
    mock_user = {
        "id": uuid.uuid4(),
        "username": "critic_test",
        "role": "critic",
    }
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_event_publisher] = lambda: mock_publisher
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    client = TestClient(app)
    yield client, mock_publisher
    app.dependency_overrides.pop(get_event_publisher, None)
    app.dependency_overrides.pop(get_db, None)


def test_create_review_schedules_created_event(authenticated_client, monkeypatch):
    """Creating a review schedules review.created event in BackgroundTasks."""
    client, mock_pub = authenticated_client
    film_id = uuid.uuid4()
    review_id = uuid.uuid4()
    body_text = "This is a comprehensive and detailed film review containing more than fifty characters."

    mock_review_obj = MagicMock()
    mock_review_obj.id = review_id
    mock_review_obj.film_id = film_id
    mock_review_obj.rating = 5
    mock_review_obj.review_body = body_text
    mock_review_obj.created_at = datetime.now(timezone.utc)
    mock_review_obj.user = MagicMock(username="critic_test")

    from handlers.review_handler import review_handler
    monkeypatch.setattr(review_handler, "create_review", AsyncMock(return_value=mock_review_obj))
    monkeypatch.setattr("routes.reviews._recalculate_film_stats_bg", AsyncMock())

    response = client.post(
        f"/api/v1/films/{film_id}/reviews",
        json={"rating": 5, "body": body_text},
    )

    assert response.status_code == 201
    assert response.json()["id"] == str(review_id)
    assert response.json()["rating"] == 5

    # Check background task was executed
    assert len(mock_pub.published_events) == 1
    event = mock_pub.published_events[0]
    assert event.event_type == "review.created"
    assert event.resource_id == str(review_id)
    assert event.timestamp.tzinfo == timezone.utc


def test_update_review_schedules_updated_event(authenticated_client, monkeypatch):
    """Updating a review schedules review.updated event in BackgroundTasks."""
    client, mock_pub = authenticated_client
    film_id = uuid.uuid4()
    review_id = uuid.uuid4()
    updated_body = "Updating the review text with significantly more than fifty characters to pass validation."

    mock_review_obj = MagicMock()
    mock_review_obj.id = review_id
    mock_review_obj.film_id = film_id
    mock_review_obj.rating = 4
    mock_review_obj.review_body = updated_body
    mock_review_obj.created_at = datetime.now(timezone.utc)
    mock_review_obj.user = MagicMock(username="critic_test")

    from handlers.review_handler import review_handler
    monkeypatch.setattr(review_handler, "update_review", AsyncMock(return_value=mock_review_obj))
    monkeypatch.setattr("routes.reviews._recalculate_film_stats_bg", AsyncMock())

    response = client.patch(
        f"/api/v1/reviews/{review_id}",
        json={"rating": 4, "body": updated_body},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(review_id)

    # Check background task was executed
    assert len(mock_pub.published_events) == 1
    event = mock_pub.published_events[0]
    assert event.event_type == "review.updated"
    assert event.resource_id == str(review_id)
