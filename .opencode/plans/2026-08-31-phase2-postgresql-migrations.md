# Phase 2: PostgreSQL & Migrations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PostgreSQL support with Alembic migrations while keeping SQLite working for dev.

**Architecture:** Keep synchronous SQLAlchemy, add psycopg2 for PostgreSQL, configure connection pooling, integrate Alembic for schema migrations. SQLite remains the default for local dev.

**Tech Stack:** SQLAlchemy (sync), psycopg2-binary, Alembic, PostgreSQL 16

**Spec:** Design approved in brainstorming session — Option A (sync + psycopg2 + Alembic).

## Global Constraints

- Python 3.10+ (pyproject.toml `requires-python = ">=3.10"`)
- ruff: line-length=120, target Python 3.10
- Existing tests must pass: `pytest -v`
- SQLite must continue to work for local dev
- No breaking changes to existing API or CLI

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `pyproject.toml` | Modify | Add `alembic`, `psycopg2-binary` dependencies |
| `netscan_lite/db.py` | Modify | Add pool settings for PostgreSQL, keep SQLite pragma |
| `alembic.ini` | Create | Alembic configuration |
| `alembic/env.py` | Create | Migration environment |
| `alembic/script.py.mako` | Create | Migration template |
| `alembic/versions/` | Create | Empty directory for migration files |
| `docker-compose.yml` | Modify | Fix `DATABASE_URL` to use `postgresql://` (no asyncpg) |
| `.env.example` | Modify | Update `DATABASE_URL` example |
| `AGENTS.md` | Modify | Add migration docs |

---

### Task 1: Add Alembic and psycopg2 dependencies

**Files:**
- Modify: `pyproject.toml:26-33`

**Interfaces:**
- Consumes: existing `[project.optional-dependencies]` list
- Produces: `alembic` and `psycopg2-binary` available for installation

- [ ] **Step 1: Add postgres optional dependency group**

Edit `pyproject.toml`, add a new optional dependency group after `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
xlsx = ["openpyxl>=3.1"]
postgres = ["psycopg2-binary>=2.9", "alembic>=1.13"]
test = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "httpx>=0.24",
]
docs = ["mkdocs-material>=9.0"]
```

- [ ] **Step 2: Verify pyproject.toml syntax**

Run: `python3 -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('OK')"``

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add alembic and psycopg2-binary for PostgreSQL migrations"
```

---

### Task 2: Configure db.py for PostgreSQL connection pooling

**Files:**
- Modify: `netscan_lite/db.py:1-32`

**Interfaces:**
- Consumes: `settings.DATABASE_URL` from config
- Produces: `engine` (SQLAlchemy engine with pool settings), `init_db()`, `get_session()`

- [ ] **Step 1: Update db.py with pool configuration**

Replace the entire content of `netscan_lite/db.py` with:

```python
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from netscan_lite.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args=connect_args,
    **(
        {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 1800,
        }
        if not _is_sqlite
        else {}
    ),
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    if _is_sqlite:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def init_db() -> None:
    """Initialize database tables using SQLModel."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency for database session."""
    with Session(engine) as session:
        yield session
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('netscan_lite/db.py').read()); print('OK')"``

- [ ] **Step 3: Commit**

```bash
git add netscan_lite/db.py
git commit -m "feat: add PostgreSQL connection pooling to db.py"
```

---

### Task 3: Initialize Alembic

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/` (empty directory)

**Interfaces:**
- Consumes: `netscan_lite.db.engine`, `netscan_lite.models` (for metadata)
- Produces: `alembic/` directory structure, `alembic.ini` config

- [ ] **Step 1: Create alembic.ini**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = sqlite:///./ns-lite.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Create alembic/env.py**

```python
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# Add project root to sys.path so we can import netscan_lite
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from netscan_lite.config import settings
from netscan_lite.models import Group, IPAddress  # noqa: F401 — ensure models are registered

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Create alembic/script.py.mako**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: Create alembic/versions/ directory**

```bash
mkdir -p alembic/versions
touch alembic/versions/.gitkeep
```

- [ ] **Step 5: Verify Alembic can detect models**

Run: `python3 -m alembic heads`
Expected: No current revisions (fresh start)

- [ ] **Step 6: Commit**

```bash
git add alembic.ini alembic/
git commit -m "feat: initialize Alembic for database migrations"
```

---

### Task 4: Generate initial migration

**Files:**
- Create: `alembic/versions/001_initial_schema.py`

**Interfaces:**
- Consumes: `netscan_lite.models` (Group, IPAddress tables)
- Produces: Initial migration that creates all tables

- [ ] **Step 1: Generate initial migration**

Run: `python3 -m alembic revision --autogenerate -m "initial schema"`
Expected: Creates a new file in `alembic/versions/`

- [ ] **Step 2: Review and clean up the generated migration**

The autogenerate should detect `groups` and `ip_addresses` tables. Review the generated file and ensure it has the correct column definitions.

- [ ] **Step 3: Verify migration applies to SQLite**

Run: `python3 -m alembic upgrade head`
Expected: Tables created in SQLite database

- [ ] **Step 4: Verify tables exist**

Run: `python3 -c "from netscan_lite.db import engine; from sqlalchemy import inspect; print(inspect(engine).get_table_names())"`
Expected: `['groups', 'ip_addresses']`

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/
git commit -m "feat: add initial schema migration"
```

---

### Task 5: Fix docker-compose.yml DATABASE_URL

**Files:**
- Modify: `docker-compose.yml:24`

**Interfaces:**
- Consumes: PostgreSQL connection string format
- Produces: Working `DATABASE_URL` using `postgresql://` (sync, not asyncpg)

- [ ] **Step 1: Update docker-compose.yml**

Change line 24 from:
```yaml
DATABASE_URL: postgresql+asyncpg://netscan:${DB_PASSWORD:-netscan_dev}@db:5432/netscan
```
To:
```yaml
DATABASE_URL: postgresql://netscan:${DB_PASSWORD:-netscan_dev}@db:5432/netscan
```

- [ ] **Step 2: Verify docker-compose.yml syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml')); print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "fix: use sync postgresql:// driver in docker-compose"
```

---

### Task 6: Update .env.example

**Files:**
- Modify: `.env.example:2`

**Interfaces:**
- Consumes: existing `.env.example`
- Produces: Updated DATABASE_URL example

- [ ] **Step 1: Update DATABASE_URL example**

Change line 2 from:
```bash
DATABASE_URL=sqlite:///./ns-lite.db
```
To:
```bash
# SQLite (default for local dev)
DATABASE_URL=sqlite:///./ns-lite.db
# PostgreSQL (for production): postgresql://user:pass@host:5432/dbname
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add PostgreSQL URL format to .env.example"
```

---

### Task 7: Update AGENTS.md with migration docs

**Files:**
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: all previous tasks
- Produces: Documented migration workflow

- [ ] **Step 1: Add migration section to AGENTS.md**

After the "Testing" section, add:

```markdown
## Database Migrations

ns-lite uses Alembic for schema migrations. SQLite is the default for local dev; PostgreSQL for production.

### Creating a migration

After changing models in `models.py`:
```bash
python3 -m alembic revision --autogenerate -m "description of change"
python3 -m alembic upgrade head
```

### Applying migrations

```bash
python3 -m alembic upgrade head
```

### Rolling back

```bash
python3 -m alembic downgrade -1
```

### Migration files

Migrations live in `alembic/versions/`. Each has a revision ID and describes schema changes.
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: add database migration guide to AGENTS.md"
```

---

### Task 8: Final verification

- [ ] **Step 1: Verify SQLite still works**

Run: `python3 -c "from netscan_lite.db import engine, init_db; init_db(); print('SQLite OK')"``

- [ ] **Step 2: Verify Alembic is configured**

Run: `python3 -m alembic heads && python3 -m alembic current`

- [ ] **Step 3: Verify all files parse correctly**

Run:
```bash
python3 -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('pyproject.toml OK')"
python3 -c "import ast; ast.parse(open('netscan_lite/db.py').read()); print('db.py OK')"
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml')); print('docker-compose.yml OK')"
```

- [ ] **Step 4: Run ruff check**

Run: `ruff check . && ruff format --check .`
Expected: PASS
