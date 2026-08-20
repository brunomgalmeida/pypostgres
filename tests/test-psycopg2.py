import logging
import os

# import psycopg2
import pypostgres
import psycopg2.extras

logging.basicConfig(
    format="%(asctime)s.%(msecs)03d: (%(name)s) %(lineno)d %(levelname)s: %(message)s",
    level=os.environ.get("LOGLEVEL", "DEBUG"),
    datefmt="%Y-%m-%d %H:%M:%S",
)

connection_details = dict(
    connect_timeout=30,
    client_encoding="utf8",
)

CONN: psycopg2.extensions.connection | None = None


def _getconnection() -> psycopg2.extensions.connection:
    """
    Get a connection to the PostgreSQL database
    """
    global CONN
    if CONN is None:
        try:
            CONN = pypostgres.connect(**connection_details)
        except psycopg2.OperationalError as ex:
            print("Failed to connect to the database. Did you start the PostgreSQL server?")
            # cd ../../docker/postgres/ docker compose down; docker compose up --wait
            raise ex
    return CONN


def test_connect():
    assert _getconnection() is not None
    print("Connection test passed.")


def test_pypostgres_object() -> None:
    obj = pypostgres.PGObject(schema="public", name="test_table", type="table")
    assert obj.full_name == "public.test_table"
    print("PGObject test passed.")


def test_cursor():
    cur = _getconnection().cursor()
    cur.execute("SELECT 1 as id;")
    result = cur.fetchone()
    logging.debug("result: %s", result)
    assert result["id"] == 1
    print("Query test passed.")


def test_server_side_cursor():
    cur = _getconnection().cursor("ServerSideCursor")
    cur.execute("SELECT 1 as id;")
    result = cur.fetchone()
    assert result["id"] == 1
    print("Server-side cursor test passed.")


def test_create_temporary_table():
    cur = _getconnection().cursor()
    cur.execute("CREATE TEMPORARY TABLE test_table (id SERIAL PRIMARY KEY, name VARCHAR(50));")
    cur.execute("INSERT INTO test_table (name) VALUES ('Test Name');")
    cur.execute("SELECT * FROM test_table;")
    result = cur.fetchall()
    print("Temporary table test result:", result)
    assert len(result) == 1
    assert result[0]["name"] == "Test Name"
    cur.execute("DROP TABLE test_table;")
    print("Temporary table test passed.")


def test_table_to_csv():
    cur = _getconnection().cursor()
    cur.execute("CREATE TABLE test_table (id SERIAL PRIMARY KEY, name VARCHAR(50));")
    print("Inserting data into test_table...")
    cur.execute("INSERT INTO test_table (name) VALUES ('Test Name 1'), ('Test Name 2');")
    # result = psycopg2_utils.exists_table(conn, schema_name="pg_catalog", table_name="pg_class")
    # assert result is True
    # print("Table existence test passed.")
    # result = psycopg2_utils.exists_table(conn, schema_name="public", table_name="non_existing_table")
    # assert result is False
    # print("Non-existing table test passed.")


# def test_utils():
#     """Test the utility functions for PostgreSQL operations."""
#     conn = _getconnection()
#     cur = conn.cursor()

#     inspector = psycopg2.utils(cur)
#     tables_in_schema = inspector.get_table_list(schema_name="pg_catalog")
#     print("Table list retrieved")
#     assert len(tables_in_schema) > 0, "No tables found in the pg_catalog schema."

#     table_exists = inspector.exists_table(table_name="pg_class", schema_name="pg_catalog")  #
#     print(f"Table exists: {table_exists}")
#     assert table_exists is True, "pg_class table should exist in pg_catalog schema."

#     pgsettings = inspector.pg_settings()
#     print("settings retrieved")
#     assert int(pgsettings["port"]) > 0, "pg_settings should return a dictionary of settings."

#     pgversion = inspector.pg_settings("server_version")
#     print(f"setting server version: {pgversion}")
#     assert pgversion is not None, "PostgreSQL server version should not be None."

#     tableschema = inspector.get_table_schema(table_name="pg_class", schema_name="pg_catalog")
#     print(f"Table schema retrieved: {tableschema}")
#     assert tableschema is not None, "Table schema for pg_class should not be None."


def test_inspect():
    """
    Test the inspector functionality to retrieve table metadata.
    This function connects to the PostgreSQL database, retrieves table names,
    indexes, foreign keys, and comments for a specific table.
    """
    conn = _getconnection()
    inspector = pypostgres.Inspector(conn)
    db = inspector.inspect()
    print(f"Database {db.name} inspected successfully.")
    for name, pgtable in db.tables.items():
        if pgtable.parent is not None:
            print(f"Table {pgtable} is a partition of {pgtable.parent.name}")
            print(pgtable.indexes)
    print("Inspector test passed.")
