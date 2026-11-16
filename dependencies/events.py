from schemas.events import ReviewEvent
from services.event_publisher import EventPublisher
from services.sqs_publisher import sqs_publisher


def get_event_publisher() -> EventPublisher:
    """
    Returns the active EventPublisher implementation.
    Can easily be swapped or mocked in unit tests without changing route code.
    """
    return sqs_publisher
