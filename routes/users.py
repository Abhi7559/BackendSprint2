from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import get_current_user
from dependencies.database import get_db
from handlers.user_handler import user_handler
from schemas.user import LoginRequest, RegisterRequest, UserResponse

router = APIRouter(
    tags=["Auth / Users"],
)


@router.post("/auth/register", response_model=UserResponse, status_code=201)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user in PostgreSQL."""
    return await user_handler.register_user(db, request)


@router.post("/auth/login")
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Simple login check against registered email."""
    return await user_handler.login_user(db, request)


@router.get("/users/me", response_model=UserResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get profile of current logged-in user."""
    return await user_handler.get_or_create_current_user(db, current_user)


@router.get("/admin/stats")
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get live counts of users and reviews from PostgreSQL."""
    return await user_handler.get_admin_stats(db)
