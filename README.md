# Day 2 - Film Review Platform API

FastAPI application for the Film Review Platform API with structured routing, services, and DAOs.

## Requirements
- Python >= 3.12
- `uv` (recommended) or `pip`

## Running the Application

Install dependencies and sync environment:
```bash
uv sync
```

Run application:
```bash
uv run uvicorn main:app --reload
```

## Running with Docker

### Option 1: Using Docker Compose (Recommended for development with hot reload)
```bash
docker compose up --build
```

### Option 2: Using Docker CLI
1. Build the image:
```bash
docker build -t film-review-api .
```

2. Run the container:
```bash
docker run -d -p 8000:8000 --name film-review-app film-review-api
```

## API Endpoints
- Health Check: `GET /health`
- Swagger UI Documentation: `GET /docs`
- ReDoc Documentation: `GET /redoc`
- Films API: `/api/v1/films`
- Reviews API: `/api/v1/reviews`
- Users API: `/api/v1/users`
