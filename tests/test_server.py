from datetime import date, datetime, time
from decimal import Decimal

from trino_mcp import server


def test_quote_identifier_escapes_double_quotes():
    assert server.quote_identifier('my"table') == '"my""table"'


def test_quote_identifier_rejects_empty_values():
    try:
        server.quote_identifier("   ")
    except ValueError as exc:
        assert str(exc) == "Identifier cannot be empty"
    else:
        raise AssertionError("Expected ValueError for empty identifier")


def test_qualified_name_quotes_all_parts():
    assert server.qualified_name("hive", "default", "orders") == '"hive"."default"."orders"'


def test_json_serializer_converts_common_types():
    payload = {
        "dt": datetime(2024, 1, 2, 3, 4, 5),
        "d": date(2024, 1, 2),
        "t": time(3, 4, 5),
        "n": Decimal("10.5"),
        "b": b"\x00\xff",
    }

    converted = server._json_serializer(payload)

    assert converted == {
        "dt": "2024-01-02T03:04:05",
        "d": "2024-01-02",
        "t": "03:04:05",
        "n": 10.5,
        "b": "00ff",
    }


def test_sample_table_rejects_out_of_range_limit():
    result = server.sample_table("hive", "default", "orders", limit=0)

    assert result == {
        "ok": False,
        "error": "limit must be between 1 and 1000",
    }


def test_sample_table_builds_expected_query(monkeypatch):
    captured = {}

    def fake_run_query(sql):
        captured["sql"] = sql
        return {"ok": True, "sql": sql, "columns": [], "row_count": 0, "rows": []}

    monkeypatch.setattr(server, "run_query", fake_run_query)

    result = server.sample_table("hive", "default", "orders", limit=5)

    assert result["ok"] is True
    assert captured["sql"] == 'SELECT * FROM "hive"."default"."orders" LIMIT 5'
