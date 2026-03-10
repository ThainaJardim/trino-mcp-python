import logging
import os
import sys
import getpass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

import trino
from trino.auth import OAuth2Authentication

from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("trino-mcp")

TRINO_HOST = os.getenv("TRINO_HOST", "trino.example.com")
TRINO_PORT = int(os.getenv("TRINO_PORT", "443"))
TRINO_USER = os.getenv("TRINO_USER", getpass.getuser())
TRINO_CATALOG = os.getenv("TRINO_CATALOG", "hive")
TRINO_SCHEMA = os.getenv("TRINO_SCHEMA", "default")
TRINO_HTTP_SCHEME = os.getenv("TRINO_HTTP_SCHEME", "https")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

_connection = None

logger.setLevel(LOG_LEVEL)


def _json_serializer(obj: Any) -> Any:
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, (list, tuple)):
        return [_json_serializer(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _json_serializer(value) for key, value in obj.items()}
    return obj


def quote_identifier(identifier: str) -> str:
    if not identifier or not identifier.strip():
        raise ValueError("Identifier cannot be empty")
    return '"' + identifier.replace('"', '""') + '"'


def qualified_name(catalog: str, schema: str, table: str | None = None) -> str:
    parts = [quote_identifier(catalog), quote_identifier(schema)]
    if table is not None:
        parts.append(quote_identifier(table))
    return ".".join(parts)


def get_connection():
    global _connection
    if _connection is not None:
        return _connection

    logger.info(
        "Opening Trino connection to %s:%s using %s",
        TRINO_HOST,
        TRINO_PORT,
        TRINO_HTTP_SCHEME,
    )
    _connection = trino.dbapi.connect(
        host=TRINO_HOST,
        port=TRINO_PORT,
        user=TRINO_USER,
        catalog=TRINO_CATALOG,
        schema=TRINO_SCHEMA,
        http_scheme=TRINO_HTTP_SCHEME,
        auth=OAuth2Authentication(),
    )
    return _connection


def run_query(sql: str) -> dict[str, Any]:
    logger.info("Executing query: %s", sql)
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        records = [dict(zip(columns, row)) for row in rows]
        return {
            "ok": True,
            "sql": sql,
            "columns": columns,
            "row_count": len(records),
            "rows": _json_serializer(records),
        }
    except Exception as exc:
        logger.exception("Query failed")
        return {
            "ok": False,
            "sql": sql,
            "error": str(exc),
        }
    finally:
        cur.close()


mcp = FastMCP("trino-mcp", json_response=True)


@mcp.tool()
def execute_query(sql: str) -> dict[str, Any]:
    """Execute an arbitrary SQL query against Trino and return a JSON-compatible payload."""
    return run_query(sql)


@mcp.tool()
def list_catalogs() -> dict[str, Any]:
    """List all catalogs available in the Trino cluster."""
    return run_query("SHOW CATALOGS")


@mcp.tool()
def list_schemas(catalog: str) -> dict[str, Any]:
    """List all schemas within a catalog."""
    return run_query(f"SHOW SCHEMAS FROM {quote_identifier(catalog)}")


@mcp.tool()
def list_tables(catalog: str, schema: str) -> dict[str, Any]:
    """List all tables within a catalog and schema."""
    return run_query(f"SHOW TABLES FROM {qualified_name(catalog, schema)}")


@mcp.tool()
def describe_table(catalog: str, schema: str, table: str) -> dict[str, Any]:
    """Describe columns and types for a specific table."""
    return run_query(f"DESCRIBE {qualified_name(catalog, schema, table)}")


@mcp.tool()
def sample_table(
    catalog: str,
    schema: str,
    table: str,
    limit: int = 20,
) -> dict[str, Any]:
    """Return a sample of rows from a specific table."""
    if limit < 1 or limit > 1000:
        return {
            "ok": False,
            "error": "limit must be between 1 and 1000",
        }

    return run_query(
        f"SELECT * FROM {qualified_name(catalog, schema, table)} LIMIT {limit}"
    )


def main() -> None:
    logger.info("Starting trino-mcp server (stdio)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
