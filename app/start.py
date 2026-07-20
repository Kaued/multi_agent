"""Wait for infrastructure dependencies before starting the API."""

from __future__ import annotations

import os
import time
import urllib.request
from collections.abc import Callable

import psycopg


def _wait_until_ready(
    name: str,
    check: Callable[[], None],
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            check()
            print(f"{name} está pronto.", flush=True)
            return
        except Exception as error:
            last_error = error
            print(f"Aguardando {name}...", flush=True)
            time.sleep(2)

    raise RuntimeError(
        f"{name} não ficou pronto em {timeout:.0f} segundos."
    ) from last_error


def _check_postgres() -> None:
    uri = os.environ["LANGGRAPH_CHECKPOINT_DB_URI"]
    with psycopg.connect(uri, connect_timeout=3) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")


def _check_qdrant() -> None:
    base_url = os.environ.get("QDRANT_URL", "http://qdrant:6333").rstrip("/")
    with urllib.request.urlopen(f"{base_url}/readyz", timeout=3) as response:
        if response.status != 200:
            raise RuntimeError(f"Qdrant respondeu com HTTP {response.status}.")


def main() -> None:
    timeout = float(os.environ.get("WAIT_FOR_SERVICES_TIMEOUT", "180"))
    _wait_until_ready("PostgreSQL", _check_postgres, timeout)
    _wait_until_ready("Qdrant", _check_qdrant, timeout)

    from app.api import main as api_main

    api_main()


if __name__ == "__main__":
    main()
