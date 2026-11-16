import abc
from schemas.events import ReviewEvent


class EventPublisher(abc.ABC):
    """
    Abstract interface for publishing domain events.
    Decouples callers (routes/handlers) from the underlying messaging technology
    (AWS SQS, RabbitMQ, Kafka, in-memory, etc.).
    """

    @abc.abstractmethod
    async def publish(self, event: ReviewEvent) -> bool:
        """
        Publish an event to the messaging system.
        Returns True if successful, False if handled failure.
        Must not raise unhandled exceptions to callers.
        """
        pass

    @abc.abstractmethod
    def check_health(self) -> bool:
        """
        Health check invoked during application startup lifespan.
        Returns True if the queue is reachable, False otherwise.
        Must never crash the application.
        """
        pass
