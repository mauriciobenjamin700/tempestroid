"""Native SQLite database capability (phase E8).

On the device the Kotlin ``DatabaseModule`` drives ``SQLiteDatabase``. On the Qt
simulator the database is *real*: queries run against a ``sqlite3`` file under
the data directory (``~/.tempestroid/app.db`` by default), so a desktop app
exercises the same SQL without a device.

Tests override the desktop database location via :func:`set_database_path`
(pointed at a ``tmp_path``) to stay isolated.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tempestroid.native.dispatch import on_device, send_native_request

__all__ = [
    "QueryResult",
    "execute",
    "execute_many",
    "set_database_path",
]


def _empty_columns() -> list[str]:
    """Provide a fresh, typed empty column-name list for default factories.

    Returns:
        A new empty list of column names.
    """
    return []


def _empty_rows() -> list[list[Any]]:
    """Provide a fresh, typed empty row list for default factories.

    Returns:
        A new empty list of rows.
    """
    return []


#: The desktop SQLite file path; ``None`` means the default under the home dir.
_database_path: Path | None = None


class QueryResult(BaseModel):
    """The result set of a SQL query.

    Attributes:
        columns: The result column names (empty for non-SELECT statements).
        rows: The result rows, each a list of column values aligned with
            :attr:`columns` (empty when nothing matched — never ``None``).
    """

    model_config = ConfigDict(frozen=True)

    columns: list[str] = Field(default_factory=_empty_columns)
    rows: list[list[Any]] = Field(default_factory=_empty_rows)


def set_database_path(path: Path | None) -> None:
    """Override the desktop database-file location (test isolation).

    Args:
        path: The SQLite file to open on the Qt simulator, or ``None`` to restore
            the default ``~/.tempestroid/app.db``.
    """
    global _database_path
    _database_path = path


def _db_path() -> Path:
    """Resolve the desktop database-file path, creating its parent dir.

    Returns:
        The SQLite file path (parent directory ensured to exist).
    """
    path = _database_path or (Path.home() / ".tempestroid" / "app.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def execute(sql: str, params: tuple[Any, ...] = ()) -> QueryResult:
    """Run a single SQL statement and return its result set.

    Args:
        sql: The SQL statement to run.
        params: The positional parameters bound to ``?`` placeholders.

    Returns:
        The :class:`QueryResult` (empty columns/rows for non-SELECT statements).
    """
    if not on_device():
        connection = sqlite3.connect(_db_path())
        try:
            cursor = connection.execute(sql, params)
            columns = (
                [description[0] for description in cursor.description]
                if cursor.description is not None
                else []
            )
            rows = [list(row) for row in cursor.fetchall()]
            connection.commit()
        finally:
            connection.close()
        return QueryResult(columns=columns, rows=rows)
    data = await send_native_request(
        "database", "execute", {"sql": sql, "params": list(params)}
    )
    return QueryResult.model_validate(data)


async def execute_many(sql: str, params_list: list[tuple[Any, ...]]) -> None:
    """Run a SQL statement once per parameter tuple in one batch.

    Args:
        sql: The SQL statement to run for each parameter tuple.
        params_list: The list of positional-parameter tuples.
    """
    if not on_device():
        connection = sqlite3.connect(_db_path())
        try:
            connection.executemany(sql, params_list)
            connection.commit()
        finally:
            connection.close()
        return
    await send_native_request(
        "database",
        "execute_many",
        {"sql": sql, "params_list": [list(params) for params in params_list]},
    )
