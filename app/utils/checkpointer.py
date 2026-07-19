import atexit
import os
import threading
from urllib.parse import quote

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_lock = threading.Lock()
_pool: ConnectionPool | None = None
_checkpointer: PostgresSaver | None = None


def _database_uri() -> str:
    """Return a psycopg-compatible URI for LangGraph checkpoints."""
    uri = os.getenv("LANGGRAPH_CHECKPOINT_DB_URI") or os.getenv("DATABASE_URL")
    if uri:
        # DATABASE_URL is also consumed by SQLAlchemy, whose driver-qualified
        # scheme is not accepted by psycopg directly.
        return uri.replace("postgresql+psycopg://", "postgresql://", 1)

    database = os.getenv("POSTGRES_DB", "agent_db")
    user = quote(os.getenv("POSTGRES_USER", "postgres"), safe="")
    password = quote(os.getenv("POSTGRES_PASSWORD", "postgres"), safe="")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def get_checkpointer() -> PostgresSaver:
    """Return the process-wide PostgreSQL checkpointer, creating it lazily."""
    global _checkpointer, _pool

    if _checkpointer is not None:
        return _checkpointer

    with _lock:
        if _checkpointer is not None:
            return _checkpointer

        min_size = int(os.getenv("LANGGRAPH_CHECKPOINT_POOL_MIN_SIZE", "1"))
        max_size = int(os.getenv("LANGGRAPH_CHECKPOINT_POOL_MAX_SIZE", "10"))
        if min_size < 0 or max_size < 1 or min_size > max_size:
            raise ValueError(
                "Invalid LangGraph checkpoint pool size: expected "
                "0 <= min_size <= max_size and max_size >= 1."
            )

        pool = ConnectionPool(
            conninfo=_database_uri(),
            min_size=min_size,
            max_size=max_size,
            open=True,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )
        try:
            pool.wait()
            checkpointer = PostgresSaver(pool)
            # setup() is idempotent and applies any pending schema migrations.
            checkpointer.setup()
        except Exception:
            pool.close()
            raise

        _pool = pool
        _checkpointer = checkpointer
        return checkpointer


def close_checkpointer() -> None:
    """Close the shared PostgreSQL connection pool, if it was opened."""
    global _checkpointer, _pool

    with _lock:
        pool = _pool
        _checkpointer = None
        _pool = None
    if pool is not None:
        pool.close()


atexit.register(close_checkpointer)
