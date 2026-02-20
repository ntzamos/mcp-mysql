# MySQL MCP Server

A read-only MCP server for MySQL (FastMCP). Supports stdio (Claude Desktop) and HTTP (Cursor, etc.).

## Tools

- `list_databases` - List all databases
- `list_tables` - List all tables in the connected database
- `run_query` - Execute read-only SQL queries

## Setup

```bash
pip install -r requirements.txt
```

## Configuration

Set `DATABASE_URL` in `.env`:

```
DATABASE_URL=mysql://user:password@host:3306/database
```

## Run

**Stdio (default – for Claude Desktop):**

```bash
python main.py
```

Add in Claude Desktop:

```bash
claude mcp add --transport stdio mysql-mcp -- python /path/to/mcp-mysql/main.py
```

Set `DATABASE_URL` in the environment (e.g. in the same `claude mcp add` with `--env`, or in your shell before starting Claude).

**HTTP (Cursor / other clients):**

```bash
MCP_TRANSPORT=streamable-http python main.py
```

Server listens on `http://0.0.0.0:8002` (or `PORT` / `BIND_HOST`).

## Optional env vars

- `BIND_HOST` - Host to bind (default: 0.0.0.0)
- `PORT` - Port for HTTP (default: 8002)
- `MCP_TRANSPORT` - `stdio` (default), `streamable-http`, or `sse`
- `DEBUG` - Set to 1/true/yes for debug logs
