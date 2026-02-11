"""
MySQL MCP Server
Provides list_databases, list_tables, and run_query tools
"""
import os
import json
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv
import pymysql
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
import uvicorn

load_dotenv()

# MySQL connection settings
DATABASE_URL = os.getenv("DATABASE_URL")

# Server settings
BIND_HOST = os.getenv("BIND_HOST", "0.0.0.0")
BIND_PORT = int(os.getenv("PORT", "8002"))


def _parse_database_url(url):
    """Parse MySQL DATABASE_URL into connection kwargs."""
    parsed = urlparse(url)
    if "@" in parsed.netloc:
        auth, hostport = parsed.netloc.rsplit("@", 1)
        user, password = auth.split(":", 1)
        user, password = unquote(user), unquote(password)
    else:
        user, password = None, None
        hostport = parsed.netloc
    host, _, port = hostport.partition(":")
    port = int(port) if port else 3306
    database = (parsed.path or "").strip("/") or None
    return {
        "host": host or "localhost",
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }


def get_connection():
    """Create a read-only MySQL connection."""
    kwargs = _parse_database_url(DATABASE_URL)
    conn = pymysql.connect(**kwargs)
    with conn.cursor() as cur:
        cur.execute("SET SESSION transaction_read_only = 1")
    return conn


def list_databases():
    """List all databases in MySQL."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys') "
                "ORDER BY schema_name"
            )
            databases = [row[0] for row in cur.fetchall()]
        return databases
    finally:
        conn.close()


def list_tables():
    """List all tables in the database."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys')
                ORDER BY table_schema, table_name
            """)
            tables = [{"schema": row[0], "table": row[1]} for row in cur.fetchall()]
        return tables
    finally:
        conn.close()


def run_query(query: str):
    """Run a read-only SQL query and return results."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return {"columns": columns, "rows": rows}
            else:
                return {"message": "Query executed (read-only mode)"}
    finally:
        conn.close()


# Create MCP Server
server = Server("mysql-mcp")


@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="list_databases",
            description="List all databases in MySQL",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="list_tables",
            description="List all tables in the database",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="run_query",
            description="Run a read-only SQL query on MySQL",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute (read-only)"
                    }
                },
                "required": ["query"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    try:
        if name == "list_databases":
            result = list_databases()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_tables":
            result = list_tables()
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "run_query":
            query = arguments.get("query")
            if not query:
                return [TextContent(type="text", text="Error: query is required")]
            result = run_query(query)
            # Convert rows to list for JSON serialization
            if "rows" in result:
                result["rows"] = [list(row) for row in result["rows"]]
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# SSE Transport setup
sse = SseServerTransport("/messages/")


async def handle_sse(scope, receive, send):
    async with sse.connect_sse(scope, receive, send) as streams:
        await server.run(
            streams[0], streams[1], server.create_initialization_options()
        )


async def handle_messages(scope, receive, send):
    await sse.handle_post_message(scope, receive, send)


async def health(scope, receive, send):
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [[b"content-type", b"text/plain"]],
    })
    await send({
        "type": "http.response.body",
        "body": b"OK",
    })


async def app(scope, receive, send):
    if scope["type"] == "http":
        path = scope.get("path", "")
        if path == "/sse":
            await handle_sse(scope, receive, send)
        elif path.startswith("/messages"):
            await handle_messages(scope, receive, send)
        elif path == "/health":
            await health(scope, receive, send)
        else:
            await send({
                "type": "http.response.start",
                "status": 404,
                "headers": [[b"content-type", b"text/plain"]],
            })
            await send({"type": "http.response.body", "body": b"Not Found"})


if __name__ == "__main__":
    print(f"Starting MySQL MCP Server on {BIND_HOST}:{BIND_PORT}")
    uvicorn.run(app, host=BIND_HOST, port=BIND_PORT)
