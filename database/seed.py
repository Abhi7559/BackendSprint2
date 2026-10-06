"""
Film Review Platform - Database Seed

Setup from an empty database:

1. Start PostgreSQL (e.g. via Docker Compose):
   docker compose up -d db

2. Configure the database URL in the project's environment configuration (.env):
   DATABASE_URL=postgresql+asyncpg://user:password@localhost/film_review

3. Apply all database migrations:
   uv run alembic upgrade head

4. Run the seed script:
   uv run python -m database.seed

5. Run the seed script again to verify idempotency:
   uv run python -m database.seed

Expected final state:
- At least 10 films across at least 3 genres
- At least 3 users with distinct roles (e.g. admin, reviewer, member)
- At least 5 reviews adhering to all validation constraints (min 50 chars, rating 1-10)
- Watchlist table exists in schema
- Running the seed script multiple times does not create duplicates
"""

import asyncio
from sqlalchemy import select
from database.engine import SessionLocal
from models.film import Film
from models.review import Review
from models.user import User


# Baseline Seed Data
SEED_USERS = [
    {
        "username": "admin_sarah",
        "email": "sarah.admin@example.com",
        "role": "admin",
    },
    {
        "username": "critic_marcus",
        "email": "marcus.critic@example.com",
        "role": "reviewer",
    },
    {
        "username": "cinephile_elena",
        "email": "elena.member@example.com",
        "role": "member",
    },
]

SEED_FILMS = [
    {
        "title": "Interstellar",
        "release_year": 2014,
        "genre": "Sci-Fi",
        "director": "Christopher Nolan",
    },
    {
        "title": "Blade Runner 2049",
        "release_year": 2017,
        "genre": "Sci-Fi",
        "director": "Denis Villeneuve",
    },
    {
        "title": "The Matrix",
        "release_year": 1999,
        "genre": "Sci-Fi",
        "director": "The Wachowskis",
    },
    {
        "title": "The Godfather",
        "release_year": 1972,
        "genre": "Drama",
        "director": "Francis Ford Coppola",
    },
    {
        "title": "The Shawshank Redemption",
        "release_year": 1994,
        "genre": "Drama",
        "director": "Frank Darabont",
    },
    {
        "title": "Parasite",
        "release_year": 2019,
        "genre": "Drama",
        "director": "Bong Joon-ho",
    },
    {
        "title": "Mad Max: Fury Road",
        "release_year": 2015,
        "genre": "Action",
        "director": "George Miller",
    },
    {
        "title": "The Dark Knight",
        "release_year": 2008,
        "genre": "Action",
        "director": "Christopher Nolan",
    },
    {
        "title": "John Wick",
        "release_year": 2014,
        "genre": "Action",
        "director": "Chad Stahelski",
    },
    {
        "title": "Spirited Away",
        "release_year": 2001,
        "genre": "Animation",
        "director": "Hayao Miyazaki",
    },
]

# Reviews reference users by email and films by (title, release_year)
SEED_REVIEWS = [
    {
        "user_email": "marcus.critic@example.com",
        "film_key": ("Interstellar", 2014),
        "rating": 9,
        "review_body": (
            "A breathtaking visual and emotional odyssey through space and time. "
            "Hans Zimmer's pipe organ score elevates every single sequence into sheer wonder."
        ),
    },
    {
        "user_email": "elena.member@example.com",
        "film_key": ("Blade Runner 2049", 2017),
        "rating": 10,
        "review_body": (
            "Roger Deakins' cinematography is immaculate in every frame. "
            "A slow-burning, meditative sci-fi masterpiece that expands on the original wonderfully."
        ),
    },
    {
        "user_email": "sarah.admin@example.com",
        "film_key": ("The Godfather", 1972),
        "rating": 10,
        "review_body": (
            "The quintessential American crime saga. "
            "Marlon Brando and Al Pacino deliver career-defining performances with unmatched narrative depth."
        ),
    },
    {
        "user_email": "marcus.critic@example.com",
        "film_key": ("Parasite", 2019),
        "rating": 10,
        "review_body": (
            "Brilliantly crafted social satire that morphs into a nail-biting thriller seamlessly. "
            "Every camera angle and set design choice carries deliberate symbolic weight."
        ),
    },
    {
        "user_email": "elena.member@example.com",
        "film_key": ("Mad Max: Fury Road", 2015),
        "rating": 9,
        "review_body": (
            "Relentless kinetic energy and practical stunt choreography at its finest. "
            "A masterclass in visual storytelling where action propels character development relentlessly."
        ),
    },
]


async def seed_database() -> None:
    print("Starting database seed...")

    async with SessionLocal() as session:
        try:
            # 1. Seed Users (stable identifier: email)
            print("Creating users...")
            user_map: dict[str, User] = {}
            created_users_count = 0

            for user_data in SEED_USERS:
                stmt = select(User).where(User.email == user_data["email"])
                existing_user = (await session.execute(stmt)).scalar_one_or_none()

                if existing_user:
                    print(f"User {user_data['email']} already exists. Skipping.")
                    user_map[user_data["email"]] = existing_user
                else:
                    user = User(
                        username=user_data["username"],
                        email=user_data["email"],
                        role=user_data["role"],
                    )
                    session.add(user)
                    await session.flush()
                    user_map[user_data["email"]] = user
                    created_users_count += 1
                    print(f"Created user: {user.username} ({user.role})")

            # 2. Seed Films (stable identifier: title + release_year)
            print("Creating films...")
            film_map: dict[tuple[str, int], Film] = {}
            created_films_count = 0

            for film_data in SEED_FILMS:
                film_key = (film_data["title"], film_data["release_year"])
                stmt = select(Film).where(
                    Film.title == film_data["title"],
                    Film.release_year == film_data["release_year"],
                )
                existing_film = (await session.execute(stmt)).scalar_one_or_none()

                if existing_film:
                    print(f"Film {film_data['title']} ({film_data['release_year']}) already exists. Skipping.")
                    film_map[film_key] = existing_film
                else:
                    film = Film(
                        title=film_data["title"],
                        release_year=film_data["release_year"],
                        genre=film_data["genre"],
                        director=film_data["director"],
                    )
                    session.add(film)
                    await session.flush()
                    film_map[film_key] = film
                    created_films_count += 1
                    print(f"Created film: {film.title} [{film.genre}]")

            # 3. Seed Reviews (stable identifier: user_id + film_id)
            print("Creating reviews...")
            created_reviews_count = 0

            for rev_data in SEED_REVIEWS:
                user = user_map[rev_data["user_email"]]
                film = film_map[rev_data["film_key"]]

                stmt = select(Review).where(
                    Review.user_id == user.id,
                    Review.film_id == film.id,
                )
                existing_review = (await session.execute(stmt)).scalar_one_or_none()

                if existing_review:
                    print(f"Review by {user.username} for '{film.title}' already exists. Skipping.")
                else:
                    review = Review(
                        film_id=film.id,
                        user_id=user.id,
                        rating=rev_data["rating"],
                        review_body=rev_data["review_body"],
                    )
                    session.add(review)
                    await session.flush()
                    created_reviews_count += 1
                    print(f"Created review for '{film.title}' by {user.username} (Rating: {review.rating}/10)")

            # Commit transaction
            print("Committing seed data...")
            await session.commit()
            print("Database seed completed successfully.")

            # Summary counts from database
            total_users = (await session.execute(select(User))).scalars().all()
            total_films = (await session.execute(select(Film))).scalars().all()
            total_reviews = (await session.execute(select(Review))).scalars().all()

            print("\nSeed completed successfully.")
            print(f"Users: {len(total_users)} (Newly added: {created_users_count})")
            print(f"Films: {len(total_films)} (Newly added: {created_films_count})")
            print(f"Reviews: {len(total_reviews)} (Newly added: {created_reviews_count})")

        except Exception as exc:
            await session.rollback()
            print(f"Error occurred during database seeding: {exc}")
            raise


if __name__ == "__main__":
    asyncio.run(seed_database())
