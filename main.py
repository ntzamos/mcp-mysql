"""
MySQL MCP Server (FastMCP)
Provides list_databases, list_tables, and run_query tools.
Supports stdio (Claude Desktop) and streamable-http/sse (Cursor, etc.).
"""
import os
import json
import logging
import ssl
from urllib.parse import urlparse, unquote, parse_qs
from dotenv import load_dotenv
import pymysql
from mcp.server.fastmcp import FastMCP

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG", "").lower() in ("1", "true", "yes") else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mysql-mcp")

DATABASE_URL = os.getenv("DATABASE_URL")
BIND_HOST = os.getenv("BIND_HOST", "0.0.0.0")
BIND_PORT = int(os.getenv("PORT", "8002"))
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")

mcp = FastMCP(
    "mysql-mcp",
    host=BIND_HOST,
    port=BIND_PORT,
    log_level="DEBUG" if os.getenv("DEBUG", "").lower() in ("1", "true", "yes") else "INFO",
)


def _parse_database_url(url):
    """Parse MySQL DATABASE_URL into connection kwargs (supports PlanetScale SSL)."""
    logger.debug("Parsing DATABASE_URL (host/user/database only)")
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
    database = (parsed.path or "").strip("/").split("?")[0] or None
    kwargs = {
        "host": host or "localhost",
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }
    qs = parse_qs(parsed.query)
    if "ssl_mode" in qs or "sslaccept" in qs or (host and "psdb.cloud" in host):
        kwargs["ssl"] = ssl.create_default_context()
        logger.debug("SSL enabled for connection")
    logger.debug("Parsed connection: host=%s port=%s user=%s database=%s", kwargs["host"], kwargs["port"], kwargs["user"], kwargs["database"])
    return kwargs


def get_connection():
    """Create a read-only MySQL connection (best-effort read-only on PlanetScale/Vitess)."""
    logger.debug("Creating MySQL connection")
    kwargs = _parse_database_url(DATABASE_URL)
    conn = pymysql.connect(**kwargs)
    try:
        with conn.cursor() as cur:
            cur.execute("SET SESSION transaction_read_only = 1")
        logger.debug("Connection established, read-only session set")
    except Exception as e:
        logger.debug("Could not set read-only session (ignored): %s", e)
    return conn


@mcp.tool(description="List all databases in MySQL.")
def list_databases() -> str:
    """List all databases in MySQL."""
    logger.debug("list_databases called")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name NOT IN ('information_schema', 'performance_schema', 'mysql', 'sys') "
                "ORDER BY schema_name"
            )
            databases = [row[0] for row in cur.fetchall()]
        logger.debug("list_databases returned %d databases: %s", len(databases), databases)
        return json.dumps(databases, indent=2)
    finally:
        conn.close()


@mcp.tool(description="List all tables in the database (schema and table name).")
def list_tables() -> str:
    """List all tables in the database."""
    logger.debug("list_tables called")
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
        logger.debug("list_tables returned %d tables", len(tables))
        return json.dumps(tables, indent=2)
    finally:
        conn.close()


@mcp.tool(description="Run a read-only SQL query on MySQL. Returns columns and rows or a message.")
def run_query(query: str) -> str:
    """Run a read-only SQL query and return results."""
    logger.debug("run_query called: %s", query[:200] + "..." if len(query) > 200 else query)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                logger.debug("run_query returned %d rows, %d columns", len(rows), len(columns))
                result = {"columns": columns, "rows": [list(row) for row in rows]}
            else:
                logger.debug("run_query executed (no result set)")
                result = {"message": "Query executed (read-only mode)"}
        return json.dumps(result, indent=2, default=str)
    finally:
        conn.close()


if __name__ == "__main__":
    transport = MCP_TRANSPORT.strip().lower()
    if transport not in ("stdio", "sse", "streamable-http"):
        transport = "stdio"
    logger.info("Starting MySQL MCP Server (transport=%s)", transport)
    if transport == "stdio":
        logger.info("Use with Claude Desktop: claude mcp add --transport stdio mysql-mcp -- python main.py")
    else:
        logger.info("HTTP server at http://%s:%s", BIND_HOST, BIND_PORT)
    mcp.run(transport=transport)
