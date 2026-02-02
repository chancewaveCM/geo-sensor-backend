# GEO Sensor Backend

AI Response Brand Citation Analyzer - Backend API

## Tech Stack

- **Framework**: FastAPI
- **Database**: SQLite (async) → PostgreSQL (production)
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Package Manager**: Poetry

## Setup

```bash
# Install dependencies
poetry install

# Initialize Alembic
poetry run alembic init alembic

# Run development server
poetry run uvicorn app.main:app --reload
```

## Endpoints

- `GET /health` - Health check
- `GET /docs` - API documentation (Swagger UI)
- `GET /api/v1/` - API v1 root

## Testing

```bash
poetry run pytest
```

## Docker

```bash
docker-compose up
```
