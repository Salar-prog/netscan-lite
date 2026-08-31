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
