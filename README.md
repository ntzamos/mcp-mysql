# MySQL MCP Server

A read-only MCP server for MySQL with SSE transport.

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

```bash
python main.py
```

Server starts on `http://0.0.0.0:8002` by default.

Optional env vars:

- `BIND_HOST` - Host to bind (default: 0.0.0.0)
- `PORT` - Port to bind (default: 8002)
