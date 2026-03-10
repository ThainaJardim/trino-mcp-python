# Trino MCP Server

Python MCP server for querying Trino with SSO via OAuth2 external authentication. It uses `trino-python-client`, launches the browser on first authenticated query, and communicates with MCP clients over `stdio`.

This repository is intended to be simple, local-first, and compatible with Cursor.

## Features

- Python 3.10+
- `trino-python-client` with `OAuth2Authentication()`
- MCP server built with `@modelcontextprotocol/python-sdk`
- `stdio` transport for Cursor compatibility
- Reusable Trino connection
- JSON-compatible responses for every tool
- Simple logging to `stderr`
- Safer identifier handling for catalog, schema, and table names

## Project structure

```text
trino_mcp/
├── server.py
└── requirements.txt
```

## Requirements

- Python 3.10+
- Network access to the target Trino cluster
- A Trino environment configured for OAuth2 / external authentication

## Quick start

Install directly from GitHub:

```bash
pip install "git+https://github.com/ThainaJardim/trino-mcp-python.git"
```

Then create a local `.cursor/mcp.json` like this:

```json
{
  "mcpServers": {
    "trino": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "trino_mcp.server"],
      "env": {
        "TRINO_HOST": "your-trino-host.example.com",
        "TRINO_PORT": "443",
        "TRINO_USER": "your-user",
        "TRINO_CATALOG": "hive",
        "TRINO_SCHEMA": "default",
        "TRINO_HTTP_SCHEME": "https"
      }
    }
  }
}
```

After reloading Cursor, test with:

- `list_catalogs`
- `execute_query` with `{ "sql": "SELECT 1 AS ok" }`

Expected behavior:

- the MCP server starts over `stdio`
- the first real query opens the browser for OAuth2 / SSO login
- after login, the query result returns as structured JSON

## Installation from source

```bash
pip install -r trino_mcp/requirements.txt
```

Or install the project itself:

```bash
pip install .
```

## Configuration

The server can be configured with environment variables.

| Variable | Default |
|---|---|
| `TRINO_HOST` | `trino.example.com` |
| `TRINO_PORT` | `443` |
| `TRINO_USER` | current OS user |
| `TRINO_CATALOG` | `hive` |
| `TRINO_SCHEMA` | `default` |
| `TRINO_HTTP_SCHEME` | `https` |
| `LOG_LEVEL` | `INFO` |

Example:

```bash
export TRINO_HOST=trino.example.com
export TRINO_PORT=443
export TRINO_USER="$USER"
export TRINO_CATALOG=hive
export TRINO_SCHEMA=default
export TRINO_HTTP_SCHEME=https
```

## Run locally

```bash
python trino_mcp/server.py
```

Or, after `pip install .`:

```bash
trino-mcp
```

Expected behavior:

- The server starts and waits for MCP requests over `stdio`
- The browser does not open immediately
- The OAuth2 login flow starts only when a tool executes the first real query

## Cursor setup

Create a local `.cursor/mcp.json` file like this:

```json
{
  "mcpServers": {
    "trino": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "trino_mcp.server"],
      "env": {
        "TRINO_HOST": "your-trino-host.example.com",
        "TRINO_PORT": "443",
        "TRINO_USER": "your-user",
        "TRINO_CATALOG": "hive",
        "TRINO_SCHEMA": "default",
        "TRINO_HTTP_SCHEME": "https"
      }
    }
  }
}
```

Why use this format:

- `command` should point to the exact Python where `trino-mcp` was installed
- `-m trino_mcp.server` avoids depending on the shell `PATH`
- `env` keeps the Trino connection settings local to the MCP server

If you are developing from a local checkout instead of installing from GitHub, this also works:

```json
{
  "mcpServers": {
    "trino": {
      "command": "/absolute/path/to/python",
      "args": ["./trino_mcp/server.py"],
      "env": {
        "TRINO_HOST": "your-trino-host.example.com",
        "TRINO_PORT": "443",
        "TRINO_USER": "your-user",
        "TRINO_CATALOG": "hive",
        "TRINO_SCHEMA": "default",
        "TRINO_HTTP_SCHEME": "https"
      }
    }
  }
}
```

The `.cursor/` directory is intentionally ignored by Git because it contains machine-specific local configuration.

## Available tools

| Tool | Description | Input |
|---|---|---|
| `execute_query` | Execute an arbitrary SQL query | `{ "sql": "SELECT 1" }` |
| `list_catalogs` | Run `SHOW CATALOGS` | `{}` |
| `list_schemas` | Run `SHOW SCHEMAS FROM <catalog>` | `{ "catalog": "hive" }` |
| `list_tables` | Run `SHOW TABLES FROM <catalog>.<schema>` | `{ "catalog": "hive", "schema": "default" }` |
| `describe_table` | Run `DESCRIBE <catalog>.<schema>.<table>` | `{ "catalog": "hive", "schema": "default", "table": "my_table" }` |
| `sample_table` | Run `SELECT * FROM <catalog>.<schema>.<table> LIMIT <limit>` | `{ "catalog": "hive", "schema": "default", "table": "my_table", "limit": 20 }` |

## Response format

Successful tool calls return a JSON-compatible object like:

```json
{
  "ok": true,
  "sql": "SHOW CATALOGS",
  "columns": ["Catalog"],
  "row_count": 2,
  "rows": [
    { "Catalog": "hive" },
    { "Catalog": "system" }
  ]
}
```

Errors are returned in a structured format:

```json
{
  "ok": false,
  "sql": "SHOW CATALOGS",
  "error": "..."
}
```

## How OAuth2 login works

This project relies on `OAuth2Authentication()` from `trino-python-client`, which supports external browser login flows. In practice:

1. Cursor calls a tool such as `list_catalogs`
2. The server opens a Trino connection
3. `trino-python-client` launches the browser for the OAuth2 login if needed
4. After authentication, the query is executed and the response is returned to Cursor

This is different from adding OAuth to the MCP server itself. The OAuth flow here is specifically for the Trino connection.

## Troubleshooting

### Cursor says the MCP server errored

The most common cause is an interpreter mismatch:

- `python` in your shell has `mcp` and `trino`
- Cursor starts the server with another interpreter such as system `python3`

Check both:

```bash
python -c "import sys; print(sys.executable); import mcp, trino; print('ok')"
python3 -c "import sys; print(sys.executable); import mcp, trino; print('ok')"
```

If only one of them works, use that exact interpreter in `.cursor/mcp.json`.

### The browser does not open

- Make sure the first tool call actually reached Trino
- Check that the environment has a GUI/browser available
- Confirm the Trino cluster is configured for OAuth2 external authentication

### Authentication keeps repeating

OAuth token caching behavior depends on the `trino-python-client` process lifetime. If the MCP process is restarted frequently, the login flow may repeat.

## Manual test

You can test the server with the MCP Inspector:

```bash
npx -y @modelcontextprotocol/inspector /absolute/path/to/python -m trino_mcp.server
```

Then call `list_catalogs` and verify that:

- the browser login opens
- the query succeeds
- the response returns structured JSON

## Development

Install development dependencies:

```bash
pip install .[dev]
```

Run tests:

```bash
pytest
```
