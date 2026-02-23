# GNIEM: Global News Intelligence & Event Monitoring System

GNIEM is an AI-powered intelligence dashboard built on top of the GDELT 2.1 dataset. It provides event retrieval, NLP-based event clustering, and time-series conflict forecasting, designed using Clean Architecture principles.

## Architecture

The project is structured into three phases:

- **Phase 1 (Completed)**: Core backend foundation, BigQuery integration, event retrieval.
- **Phase 2 (Completed)**: AI Analytics (NLP Clustering, Time-Series Forecasting).
- **Phase 3 (Upcoming)**: Frontend dashboard and advanced live analytics.

The current backend is built with FastAPI, Pydantic, and Clean Architecture:

1. **Domain Layer (`domain/`)**: Pure business logic, containing `Event`, `EventFilter`, `EventCluster`, `ForecastResult` models. Defines interfaces (`ports`) for external services.
2. **Application Layer (`application/`)**: Use cases orchestrating domain models and ports (`GetEventsUseCase`, `ClusterEventsUseCase`, `ForecastEventsUseCase`).
3. **Infrastructure Layer (`infrastructure/`)**: Concrete implementations of ports (`GdeltRepository`, `BigQueryClient`, `Settings`).
4. **API Layer (`api/`)**: FastAPI routers and schemas, wiring dependencies together and exposing HTTP endpoints.

## Dependencies

- **FastAPI** / **Uvicorn**: High-performance HTTP API.
- **Google Cloud BigQuery**: Used as the primary data warehouse for GDELT data.
- **scikit-learn** & **numpy**: Used for TF-IDF event vectorization and KMeans clustering.
- **prophet**: Facebook's Prophet library used for robust time-series conflict forecasting.

## Setup and Installation

### 1. Environment Variables

Create a `.env` file in the project root (a template `.env.example` is provided):

```ini
GCP_PROJECT_ID=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
# Optional Overrides:
GDELT_DATASET=gdelt-bq.gdeltv2
GDELT_TABLE=events
ENVIRONMENT=development
LOG_LEVEL=INFO
```

> **Note:** A valid GCP service account with BigQuery read access is required for local execution.

### 2. Local Development (Virtual Environment)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Run the server
PYTHONPATH=. uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Docker setup

```bash
docker-compose up --build
```
This mounts your service account and exposes the API on port 8000.

### 4. Running Tests

```bash
source .venv/bin/activate
pip install pytest pytest-asyncio httpx
PYTHONPATH=. pytest backend/tests/unit/ -v
```
Tests mock all BigQuery and ML calls, so they can run offline.

## API Endpoints Summary

Once the application is running, visit `http://localhost:8000/docs` for the interactive Swagger UI.

### Health
- `GET /api/v1/health` - Check BigQuery connectivity and service uptime.

### Events
- `GET /api/v1/events` - Retrieve generic events with optional filters (limit, dates, country).
- `GET /api/v1/events/region/{country_code}` - Get events for a specific ISO country code.
- `GET /api/v1/events/counts` - Global daily event counts for charting.
- `GET /api/v1/events/counts/{country_code}` - Daily event counts isolated to one country.

### AI Analytics (Phase 2)
- `GET /api/v1/analytics/clusters` - Groups semantic events together using TF-IDF & KMeans.
- `GET /api/v1/analytics/forecast` - Global time-series conflict forecasting using Prophet.
- `GET /api/v1/analytics/forecast/{country_code}` - Regional conflict forecasting.
