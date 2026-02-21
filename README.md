# Delivery Tracking Platform

A production-ready, event-driven microservices platform for real-time delivery tracking. Customers track shipments live, couriers update locations and statuses, and admins manage dispatch, assignments, and exceptions.

---

## Overview

**What You're Building**

A platform that lets customers track deliveries in real time, couriers update location + delivery status from a driver app, and admins/ops manage shipments, assignments, exceptions, and performance. The system is event-driven (Kafka), low-latency for tracking (Redis + WebSocket), and built as microservices with clean boundaries and production-grade practices (auth, migrations, CI/CD, observability, resiliency).

---

## Personas

- **Customer**: Creates shipment order, receives tracking link, watches live ETA + status, gets notifications.
- **Courier/Driver**: Accepts assignment, shares GPS pings, updates statuses (picked up, in transit, delivered).
- **Admin/Ops**: Manages hubs, zones, assignments, exceptions (failed delivery), dashboards.

---

## Core User Journeys (MVP)

1. **Create Shipment** → Shipment gets an ID + tracking code.
2. **Assign Courier** (manual or auto) → Courier gets notified.
3. **Live Tracking** → Courier sends location pings → Customer sees movement + ETA.
4. **Status Timeline** → "Created → Picked up → In transit → Out for delivery → Delivered/Failed".
5. **Notifications** → Email/push/webhook when key events happen.
6. **Audit & Analytics** → Delivery times, failure reasons, courier performance.

---

## Non-Functional Goals

- **Reliability**: Retries, idempotency, dead-letter topics, outbox pattern.
- **Scalability**: Async event processing; caching hot reads; horizontal scaling.
- **Observability**: Structured logs, metrics, tracing, correlation IDs.
- **Security**: JWT/OAuth2, RBAC, rate limiting, secrets management.
- **Delivery Speed**: CI/CD, migrations, fast local dev with docker-compose.

---

## Tech Stack

### Backend
- **Framework**: FastAPI (per service), Pydantic settings
- **Database**: PostgreSQL (per-service DB or schemas), SQLAlchemy/SQLModel
- **Migrations**: Alembic
- **Caching & Pub/Sub**: Redis
- **Event Streaming**: Kafka
- **Real-Time**: WebSocket (or SSE)

### Infrastructure & DevOps
- **Containerization**: Docker + docker-compose (local)
- **Orchestration**: Kubernetes (optional later) + Helm (optional)
- **Gateway**: Nginx / API Gateway (or Traefik)
- **CI/CD**: GitHub Actions (lint, tests, build images, push, deploy)
- **Observability**: OpenTelemetry + Prometheus + Grafana + Loki

### Optional (Impressive Additions)
- PostGIS for geospatial queries (nearby couriers, zones)
- Object storage (S3/R2) for proof-of-delivery images

---

## Service Boundaries (Microservices)

Each service owns its own data. Other services access it via API calls or Kafka events.

### Core Services (MVP)

| Service | Purpose | Database |
|---------|---------|----------|
| **API Gateway / BFF** | Public entry point, auth, rate-limit, routing | — |
| **Auth & Users Service** | Users, roles (customer/courier/admin), JWT issuing/validation | PostgreSQL |
| **Shipments Service** | Shipment creation, addresses, package details, tracking code | PostgreSQL |
| **Dispatch Service** | Assignment logic (manual first, later auto), courier availability | PostgreSQL |
| **Tracking Service** | Location ingest, status timeline, "current state" reads (hot path) | PostgreSQL + Redis |
| **Notifications Service** | Subscribes to events → sends email/push/webhooks | Optional (stateless) |

### Later Services (Phase 5+)

- **Analytics Service**: Aggregations, KPIs, dashboards
- **Admin Service**: Ops UI endpoints, exception management, zones/hubs

---

## Event-Driven Backbone (Kafka)

### Topics (Starter Set)

- `shipment.created`
- `shipment.assigned`
- `courier.location_updated`
- `shipment.status_updated`
- `delivery.completed`
- `delivery.failed`
- `notification.requested` (optional internal command topic)
- `deadletter.*` (DLQ per consumer group)

### Event Standards

Every event includes:
- `event_id` (UUID)
- `event_type`
- `occurred_at`
- `correlation_id` (ties a whole flow together)
- `producer`, `version`

**Rules:**
- Consumers must be idempotent (safe to process duplicates).
- Use Outbox pattern in producer services (write DB + publish event reliably).

---

## Data Ownership Rule

- Each service owns its data. Other services don't query that DB directly.
- Cross-service workflows happen through Kafka events and API calls.
- **Cache Storage**: Redis holds "latest location", "latest status", active tracking sessions.

---

## Public API Surface

### REST Endpoints (Examples)

- `POST /shipments` — Create shipment (customer/admin)
- `GET /shipments/{tracking_code}` — Public tracking view (limited fields)
- `GET /shipments/{id}` — Authorized details
- `POST /shipments/{id}/assign` — Assign courier (admin/dispatch)
- `POST /tracking/{shipment_id}/location` — Courier location ping
- `POST /shipments/{id}/status` — Courier status update
- `GET /shipments/{id}/timeline` — Status timeline (customer/admin)

### Real-Time

- `WS /track/{tracking_code}` — WebSocket live updates for customers

---

## Build Phases & Milestones

### Phase 0: Product & Architecture Freeze (1–2 days)
- Define statuses, roles, event list, topic naming, service boundaries
- Decide DB per service + local docker-compose architecture
- **Exit**: Architecture diagram + topic list + API list written

### Phase 1: Repo + Dev Foundation (Must Be Solid)
- Monorepo with `/services/*`
- docker-compose: Postgres, Redis, Kafka (+ optional Redpanda Console)
- Shared tooling: lint/format, pre-commit, Makefile, env templates
- Base FastAPI template per service (healthcheck, config, logging, OpenAPI, migrations)
- **Exit**: `docker compose up` runs everything, one service boots cleanly

### Phase 2: Auth & Users (RBAC + JWT)
- Auth service: register/login, JWT, refresh tokens
- Roles: customer, courier, admin
- Gateway validates JWT
- **Exit**: Protected endpoints working; role-based access enforced

### Phase 3: Shipments (Core Domain)
- Shipments service: create shipment, generate tracking code, read shipment
- Produce Kafka event `shipment.created`
- Notifications listens (mocked initially)
- **Exit**: Create shipment → stored in DB → event published → consumer receives

### Phase 4: Dispatch (Assignment Workflow)
- Dispatch service: assign courier to shipment
- Event `shipment.assigned`
- Courier "inbox" endpoint
- **Exit**: Admin assigns → dispatch DB updated → courier sees assignment

### Phase 5: Tracking (Real-Time + Cache)
- Tracking ingest endpoint for courier GPS pings
- Store history (DB) + store "latest state" in Redis
- Status updates endpoint (picked up, in transit, delivered…)
- WebSocket/SSE endpoint for customer live updates
- Events: `courier.location_updated`, `shipment.status_updated`
- **Exit**: Courier sends location → Redis latest updates → customer sees live movement

### Phase 6: Notifications (Real Channels)
- Email provider integration (or mocked adapter with logs)
- Notification preferences
- Triggers from events (assigned, out-for-delivery, delivered, failed)
- **Exit**: Key events reliably produce notifications (with retry + DLQ)

### Phase 7: Observability & Resiliency (Make It "Prod")
- OpenTelemetry tracing across gateway → services → Kafka consumers
- Metrics + dashboards (request latency, consumer lag, error rates)
- Structured logging with correlation_id
- Retry policies, circuit breaker, DLQ handling
- **Exit**: Trace one shipment end-to-end; see failures clearly

### Phase 8: Security Hardening + Performance
- Rate limiting (gateway), input validation, least-privilege service accounts
- Secrets handling (env + vault-like later)
- Caching strategy for hot reads
- Load test basic flows (k6/Locust)
- **Exit**: System handles load; security basics in place

### Phase 9: Deployment (Staging → Production)
- CI/CD pipeline: test → build images → push → deploy
- IaC (Terraform optional) + staging environment
- Versioned configs, DB migrations in pipeline
- **Exit**: One-click deploy to staging; reproducible releases

---

## Getting Started

```bash
# Clone and setup
git clone <repo>
cd dtp

# Start services locally
docker compose up

# Run migrations
make migrate

# Access services
# - API Gateway: http://localhost:8000
# - Redpanda Console: http://localhost:8080 (if included)
```

---

## Project Structure

```
dtp/
├── docker-compose.yml       # Local dev environment
├── Makefile                 # Build & dev commands
├── pyproject.toml           # Shared Python dependencies
├── services/
│   ├── auth-service/        # Auth & Users
│   ├── shipments-service/   # Shipments (Core)
│   ├── dispatch-service/    # Dispatch & Assignments
│   ├── tracking-service/    # Tracking & Location
│   ├── notifications-service/ # Notifications
│   └── gateway/             # API Gateway / BFF
└── docs/
    ├── architecture.md      # Service diagram & data flow
    ├── events.md            # Kafka topic & event schemas
    └── api.md               # API specifications
```

---

## Key Design Principles

1. **Single Responsibility**: Each service does one thing well.
2. **Data Isolation**: Own your database; talk via API or events.
3. **Event-Driven**: Async workflows; reliable with outbox pattern.
4. **Idempotency**: Safe to replay events or retry operations.
5. **Observability**: Correlation IDs; structured logs; tracing.
6. **Fast Local Dev**: docker-compose up and go; migrations automated.

---

## Next Steps

1. ✅ Lock architecture & service boundaries
2. 🚀 Set up monorepo, docker-compose, Makefile
3. 🔐 Implement Auth & Users (JWT + RBAC)
4. 📦 Implement Shipments (create, track code, persist)
5. 🚚 Build Dispatch (assignments, availability)
6. 📍 Add Tracking (GPS ingest, real-time WebSocket)
7. 💬 Add Notifications (email, webhooks, retries)
8. 📊 Add Observability (tracing, metrics, logs)
9. 🛡️ Secure & load test
10. 🚀 Deploy to staging & production

---

**Status**: In Development (Phase 0–1)
