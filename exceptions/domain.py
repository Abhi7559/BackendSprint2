from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    CRITIC = "critic"
    VIEWER = "viewer"


class DomainError(Exception):
    """Base exception for all domain business errors."""
    pass


class FilmNotFoundError(DomainError):
    """Raised when a requested film is not found or has been soft-deleted."""
    def __init__(self, film_id: object):
        self.film_id = film_id
        super().__init__(f"Film {film_id} was not found.")


class ReviewNotFoundError(DomainError):
    """Raised when a requested review is not found."""
    def __init__(self, review_id: object):
        self.review_id = review_id
        super().__init__(f"Review {review_id} was not found.")


class DuplicateReviewError(DomainError):
    """Raised when a user attempts to submit more than one review for the same film."""
    def __init__(self, user_id: object, film_id: object):
        self.user_id = user_id
        self.film_id = film_id
        super().__init__(f"User {user_id} has already reviewed film {film_id}.")


class UnauthorisedReviewAccessError(DomainError):
    """Raised when a user attempts to modify a review they do not own."""
    def __init__(self, review_id: object, user_id: object):
        self.review_id = review_id
        self.user_id = user_id
        super().__init__(f"User {user_id} is not allowed to modify review {review_id}.")


class FilmHasActiveReviewsError(DomainError):
    """Raised when attempting to delete a film that still has active reviews."""
    def __init__(self, film_id: object):
        self.film_id = film_id
        super().__init__(f"Film {film_id} cannot be deleted because it has active reviews.")


class EmailAlreadyExistsError(DomainError):
    """Raised when registering with an email that is already in use."""
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"Email '{email}' is already registered.")


class UsernameAlreadyExistsError(DomainError):
    """Raised when registering with a username that is already in use."""
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"Username '{username}' is already taken.")


class InvalidCredentialsError(DomainError):
    """Raised when authentication credentials are invalid."""
    def __init__(self):
        super().__init__("Invalid username or password.")


class InvalidTokenError(DomainError):
    """Raised when JWT token is expired, invalid, or malformed."""
    def __init__(self, detail: str = "Invalid or expired token."):
        self.detail = detail
        super().__init__(detail)


class ForbiddenError(DomainError):
    """Raised when user does not have sufficient role/permissions (403)."""
    def __init__(self, detail: str = "Access forbidden: insufficient role permissions."):
        self.detail = detail
        super().__init__(detail)
