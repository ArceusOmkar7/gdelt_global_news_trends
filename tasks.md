# GNIEM Project Tasks

## Phase 1: Foundation (Completed)
- [x] Set up FastAPI app with Clean Architecture structure
- [x] Create BigQuery client and repository
- [x] Implement event retrieval domain models and use cases
- [x] Establish health check and event endpoints
- [x] Unit tests for Phase 1

## Phase 2: AI Analytics (Completed)
- [x] Implement NLP clustering service (TF-IDF + KMeans)
- [x] Implement time-series forecasting service (Prophet)
- [x] Integrate ML models with domain models and use cases
- [x] Create `/api/v1/analytics/clusters` and `/api/v1/analytics/forecast` endpoints
- [x] Unit tests for AI analytics models and services
- [x] Fix BigQuery dataset access permissions to `gdelt-bq.gdeltv2`

## Phase 3: Frontend & Advanced Features (To Do)
- [ ] Initialize frontend application (React/Vue/Svelte)
- [ ] Build interactive mapping dashboard
- [ ] Connect frontend to `/api/v1/events` endpoints
- [ ] Visualize event clusters and forecasting curves
- [ ] Enhance clustering service to process real article text from `source_url`
- [ ] Add deployment configuration (Docker Swarm/K8s)
