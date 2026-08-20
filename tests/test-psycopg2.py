import csv
import logging
import os
from io import StringIO

import psycopg2
import psycopg2.extras
import pytest

import pypostgres
from pypostgres.pgutils import PGUtils

logging.basicConfig(
    format="%(asctime)s.%(msecs)03d: (%(name)s) %(lineno)d %(levelname)s: %(message)s",
    level=os.environ.get("LOGLEVEL", "DEBUG"),
    datefmt="%Y-%m-%d %H:%M:%S",
)

connection_details = dict(
    connect_timeout=30,
    client_encoding="utf8",
)

CONN = None


def _getconnection():
    global CONN
    if CONN is None:
        try:
            CONN = pypostgres.connect(**connection_details)
        except psycopg2.OperationalError as ex:
            print("Failed to connect to the database. Did you start the PostgreSQL server?")
            raise ex
    return CONN


# == Connection ==

def test_connect():
    assert _getconnection() is not None


def test_connect_returns_custom_cursor():
    conn = _getconnection()
    cur = conn.cursor()
    assert isinstance(cur, pypostgres.CustomCursor)
    cur.close()


def test_connect_custom_cursor_factory():
    conn = pypostgres.connect(cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()
    result = cur.execute("SELECT 1 as id").fetchone() or cur.fetchone()
    cur.close()
    conn.close()


def test_wait_callback_registered():
    assert psycopg2.extensions.get_wait_callback() is not None


def test_dict_adapter_registered():
    adapted = psycopg2.extensions.adapt(dict({"key": "value"}))
    assert adapted is not None


# == Cursor ==

def test_cursor_dict_style():
    cur = _getconnection().cursor()
    cur.execute("SELECT 1 as id, 'hello' as name")
    result = cur.fetchone()
    assert result["id"] == 1
    assert result["name"] == "hello"
    cur.close()


def test_server_side_cursor():
    cur = _getconnection().cursor("ServerSideCursor")
    cur.execute("SELECT 1 as id;")
    result = cur.fetchone()
    assert result["id"] == 1
    cur.close()


# == CustomCursor.to_csv ==

def test_to_csv_to_file():
    cur = _getconnection().cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS _test_csv_export (id SERIAL PRIMARY KEY, name VARCHAR(50))")
    cur.execute("INSERT INTO _test_csv_export (name) VALUES ('Alice'), ('Bob'), ('Charlie')")
    cur.execute("SELECT id, name FROM _test_csv_export ORDER BY id")
    filepath = cur.to_csv("/tmp/_test_export.csv")
    assert filepath is not None
    with open("/tmp/_test_export.csv") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 3
    assert rows[0]["name"] == "Alice"
    assert rows[2]["name"] == "Charlie"
    cur.execute("DROP TABLE _test_csv_export")
    cur.close()
    os.remove("/tmp/_test_export.csv")


def test_to_csv_to_stringio():
    cur = _getconnection().cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS _test_csv_stringio (id SERIAL PRIMARY KEY, val INT)")
    cur.execute("INSERT INTO _test_csv_stringio (val) VALUES (10), (20)")
    cur.execute("SELECT id, val FROM _test_csv_stringio ORDER BY id")
    result = cur.to_csv()
    assert result is not None
    content = result.getvalue()
    assert "val" in content
    assert "10" in content
    cur.execute("DROP TABLE _test_csv_stringio")
    cur.close()


def test_to_csv_empty_result():
    cur = _getconnection().cursor()
    cur.execute("SELECT 1 as id WHERE 1=0")
    result = cur.to_csv()
    assert result is None
    cur.close()


# == PGUtils ==

def test_utils_get_table_list():
    conn = _getconnection()
    cur = conn.cursor()
    utils = PGUtils(cur)
    tables = utils.get_table_list(schema_name="pg_catalog")
    assert len(tables) > 0
    cur.close()


def test_utils_exists_table_true():
    conn = _getconnection()
    cur = conn.cursor()
    utils = PGUtils(cur)
    assert utils.exists_table(table_name="pg_class", schema_name="pg_catalog") is True
    cur.close()


def test_utils_exists_table_false():
    conn = _getconnection()
    cur = conn.cursor()
    utils = PGUtils(cur)
    assert utils.exists_table(table_name="nonexistent_table_xyz", schema_name="public") is False
    cur.close()


def test_utils_pg_settings_all():
    conn = _getconnection()
    cur = conn.cursor()
    utils = PGUtils(cur)
    settings = utils.pg_settings()
    assert isinstance(settings, dict)
    assert "port" in settings
    assert int(settings["port"]) > 0
    cur.close()


def test_utils_pg_settings_single():
    conn = _getconnection()
    cur = conn.cursor()
    utils = PGUtils(cur)
    version = utils.pg_settings("server_version")
    assert version is not None
    cur.close()


def test_utils_get_table_schema():
    conn = _getconnection()
    cur = conn.cursor()
    utils = PGUtils(cur)
    table = utils.get_table_schema(table_name="pg_class", schema_name="pg_catalog")
    assert table is not None
    assert table.name == "pg_class"
    assert table.schema == "pg_catalog"
    assert len(table.column) > 0
    cur.close()


def test_utils_create_temporary_table():
    conn = _getconnection()
    cur = conn.cursor()
    utils = PGUtils(cur)
    utils.create_temporary_table(
        "_test_pgutils_temp",
        {"id": "SERIAL PRIMARY KEY", "name": "VARCHAR(50)"},
    )
    cur.execute("INSERT INTO _test_pgutils_temp (name) VALUES ('test')")
    cur.execute("SELECT * FROM _test_pgutils_temp")
    result = cur.fetchall()
    assert len(result) == 1
    assert result[0]["name"] == "test"
    cur.close()


def test_utils_get_foreign_keys():
    conn = _getconnection()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS _test_fk_parent (id SERIAL PRIMARY KEY)")
    cur.execute("CREATE TABLE IF NOT EXISTS _test_fk_child (id SERIAL PRIMARY KEY, parent_id INT REFERENCES _test_fk_parent(id))")
    utils = PGUtils(cur)
    fks = utils.get_foreign_keys("_test_fk_parent", schema_name="public")
    assert len(fks) == 1
    assert fks[0]["referenced_table_name"] == "_test_fk_parent"
    assert fks[0]["referencing_table_name"] == "_test_fk_child"
    cur.execute("DROP TABLE _test_fk_child")
    cur.execute("DROP TABLE _test_fk_parent")
    cur.close()


def test_utils_get_foreign_keys_empty():
    conn = _getconnection()
    cur = conn.cursor()
    utils = PGUtils(cur)
    fks = utils.get_foreign_keys("_test_fk_parent", schema_name="public")
    assert len(fks) == 0
    cur.close()


# == Dict adapter ==

def test_dict_insert_as_json():
    conn = _getconnection()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS _test_dict_json (id SERIAL PRIMARY KEY, data JSONB)")
    cur.execute("INSERT INTO _test_dict_json (data) VALUES (%s)", ({"key": "value", "num": 42},))
    cur.execute("SELECT data FROM _test_dict_json")
    result = cur.fetchone()
    assert result["data"]["key"] == "value"
    assert result["data"]["num"] == 42
    cur.execute("DROP TABLE _test_dict_json")
    cur.close()


# == Inspector ==

def test_inspect():
    conn = _getconnection()
    inspector = pypostgres.Inspector(conn)
    db = inspector.inspect()
    assert db is not None
    assert db.name == "postgres"
    assert len(db.schemas) > 0
    assert len(db.tables) > 0
    for name, pgtable in db.tables.items():
        if pgtable.parent is not None:
            assert pgtable.parent is not None
    assert db is not None


def test_inspect_returns_schemas():
    conn = _getconnection()
    inspector = pypostgres.Inspector(conn)
    db = inspector.inspect()
    schema_names = [s.name for s in db.schemas]
    assert "public" in schema_names or "pg_catalog" in schema_names
