# Second Serving

**Second Serving** is a mobile-first backend for a food waste reduction app. It helps households track grocery inventory, receive expiry alerts, discover recipes that use items near expiry, and sync data across devices — all powered by a FastAPI REST API backed by PostgreSQL.

---

## Stack

| Layer | Technology |
|:---|:---|
| Framework | FastAPI 0.110 + Uvicorn (ASGI) |
| Database | PostgreSQL 15 |
| ORM / Migrations | SQLAlchemy 2.0 + Alembic |
| Authentication | JWT (python-jose) + bcrypt 4.0.1 |
| Push Notifications | Firebase Admin SDK (FCM) |
| Background Jobs | APScheduler (BackgroundScheduler) |
| Validation | Pydantic v2 |
| Deployment target | AWS EC2 |

---

## Project Structure

```
backend_app/
├── app/
│   ├── main.py                  # FastAPI app factory, routers, exception handlers, scheduler
│   ├── config.py                # Settings via @lru_cache singleton (reads .env)
│   ├── database.py              # SQLAlchemy engine + SessionLocal + Base
│   │
│   ├── common/                  # Shared utilities
│   │   ├── dependencies.py      # get_db(), get_current_user() (JWT guard)
│   │   ├── exceptions.py        # AppException(HTTPException) + ErrorCode constants
│   │   ├── error_handlers.py    # 4 global async handlers (RFC 7807 format)
│   │   └── response.py          # success_response() / error_response() helpers
│   │
│   ├── auth/                    # User registration & JWT login
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── router.py
│   │
│   ├── inventory/               # Grocery item CRUD + consume/discard events
│   │   ├── models.py            # InventoryItem, InventoryEvent
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── router.py
│   │
│   ├── notifications/           # FCM push notification scheduling
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py           # send_expiry_alerts() called by APScheduler
│   │   └── router.py
│   │
│   ├── recipes/                 # Recipe suggestions ranked by expiry urgency
│   │   ├── models.py            # Recipe, RecipeIngredient, RecipeInteraction
│   │   ├── schemas.py
│   │   ├── service.py           # Scoring algo + seed_recipes()
│   │   └── router.py
│   │
│   ├── analytics/               # Read-only dashboard metrics (CQRS)
│   │   ├── schemas.py
│   │   ├── service.py           # Savings, waste trends, user segment
│   │   └── router.py
│   │
│   └── sync/                    # Offline-first delta synchronization
│       ├── models.py            # SyncLog
│       ├── schemas.py
│       ├── service.py           # push_changes / pull_changes (LWW)
│       └── router.py
│
├── alembic/
│   ├── env.py                   # Imports all models for autogenerate
│   └── versions/
│       ├── 25011f214fde_*.py    # Base: users + inventory tables
│       ├── a1b2c3d4e5f6_create_recipes_and_sync_tables.py
│       └── b2c3d4e5f6a1_add_analytics_indexes.py
│
├── .env                         # Local secrets (never committed)
├── requirements.txt
├── alembic.ini
└── SecondServing.postman_collection.json
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              Mobile Clients                  │
│           (iOS / Android / Web)              │
└────────────────────┬────────────────────────┘
                     │ HTTPS / JSON
┌────────────────────▼────────────────────────┐
│            FastAPI  (ASGI / Uvicorn)         │
│  ┌──────────────────────────────────────┐   │
│  │  Global Exception Handlers           │   │
│  │  (RFC 7807 Problem Details format)   │   │
│  └──────────────────────────────────────┘   │
│  ┌──────────────────────────────────────┐   │
│  │  Routers  (auth / inventory /        │   │
│  │   notifications / recipes /          │   │
│  │   analytics / sync)                  │   │
│  └────────────────┬─────────────────────┘   │
│  ┌────────────────▼─────────────────────┐   │
│  │  Services  (business logic)          │   │
│  └────────────────┬─────────────────────┘   │
│  ┌────────────────▼─────────────────────┐   │
│  │  ORM Models  (SQLAlchemy 2.0)        │   │
│  └────────────────┬─────────────────────┘   │
└───────────────────┼─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│            PostgreSQL 15                     │
└─────────────────────────────────────────────┘
         ▲
         │ every 1 h
┌────────┴────────────────────────────────────┐
│  APScheduler  →  send_expiry_alerts()        │
│                    │                         │
│                    └──►  FCM (Firebase)       │
└─────────────────────────────────────────────┘
```

### Module Responsibilities

| Module | Responsibility |
|:---|:---|
| `auth` | Register, login, JWT issuance |
| `inventory` | CRUD items, consume/discard with event log |
| `notifications` | FCM token registration, hourly expiry push alerts |
| `recipes` | Suggestion scoring, cooked interaction (auto-consumes items) |
| `analytics` | Read-only aggregations: savings, waste trends, user segment |
| `sync` | Delta push/pull for offline-capable clients (Last-Write-Wins) |

---

## Design Patterns

| Pattern | Where applied |
|:---|:---|
| **Layered Architecture** | Router → Service → ORM → DB. Each layer has a single responsibility. |
| **Feature Modules** | Each domain lives in its own folder with `models / schemas / service / router`. |
| **Dependency Injection** | `get_db()` and `get_current_user()` injected via FastAPI `Depends()`. |
| **DTO / Schema Separation** | Pydantic schemas decouple the API contract from ORM models. |
| **Event Sourcing (lightweight)** | `InventoryEvent` log records every consume/discard action immutably. |
| **CQRS** | `analytics` module is read-only; it queries the event log without mutating state. |
| **Singleton** | `get_settings()` uses `@lru_cache` — the `Settings` object is created once. |
| **RFC 7807 Error Structure** | All error responses share `{status, code, message, details, timestamp}`. |
| **Last-Write-Wins (LWW)** | Sync conflicts resolved by comparing `client_timestamp` vs `server_timestamp`. |

---

## Initialization

### 1. Clone and create virtual environment

```bash
git clone <repo-url>
cd backend_app
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create the database

```bash
createdb second_serving   # or use psql / pgAdmin
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
# Application
APP_NAME=Second Serving
APP_ENV=development

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/second_serving

# JWT
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Firebase (FCM)
FIREBASE_CREDENTIALS_PATH=path/to/firebase-adminsdk.json
```

### 5. Run migrations

```bash
alembic upgrade head
```

### 6. Seed recipes (optional)

```bash
curl -X POST http://localhost:8000/api/v1/recipes/seed
```

---

## Running the Project

### Development (auto-reload)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Health check

```bash
curl http://localhost:8000/api/v1/health
# {"status":"ok","environment":"development","app":"Second Serving"}
```

### Interactive API docs

Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.

---

## Development Workflow

### 📅 Project Hierarchy

Each Sprint acts as a milestone and contains a flexible number of **MicroSprints (MS)** for iterative delivery.

* **Sprint 1 - 4:** High-level project phases/milestones.
* **MicroSprints (MS):** Weekly execution cycles within a Sprint.

---

### 🏷️ Issue Naming Convention

All issue titles must follow the standard pattern:
`[SCOPE][S-X][MS-Y] Brief descriptive title`

#### 1. Scope Prefixes (`[SCOPE]`)
| Prefix | Name | Description |
| :--- | :--- | :--- |
| **`[IND]`** | Individual | Tasks assigned to and executed by a single owner. |
| **`[GRP]`** | Group | Collaborative efforts (Pair programming, brainstorming, meetings). |

#### 2. Sprint & MicroSprint Tracking
* **`[S-X]`**: The Main Sprint number (1 to 4).
* **`[MS-Y]`**: The MicroSprint number within that specific phase.

#### 💡 Examples
* `[IND][S-1][MS-2] Put sticky notes with your ideas about how to solve the problem`
* `[GRP][S-2][MS-1] Discuss all the ideas about how to solve the problem`
* `[IND][S-3][MS-4] Vote for your favorite ideas`

---

### 🚦 Workflow & Statuses

We utilize the **GitHub Project Board** with the following pipeline:

1. **Todo:** Refined tasks ready to be started.
2. **In Progress:** Tasks currently under development.
3. **In Review:** Pull Requests (PRs) or tasks awaiting peer feedback/QA.
4. **Done:** Successfully tested and merged into the main branch.

---

### 📝 Issue Structure Requirement

When creating an issue, please ensure it meets the **Definition of Ready (DoR)**:

#### 🎯 Context
Brief explanation of the "Why" and the user value.

#### 🛠️ Technical Implementation
List of systems involved (e.g., Twilio Studio, Intercom API, Azure Functions).

### ✅ Checklist (Definition of Done)
- [ ] Task A
- [ ] Task B
- [ ] Unit testing/Manual validation

### 🚩 Acceptance Criteria
- Must handle [X] condition.
- Must return [Y] response.
