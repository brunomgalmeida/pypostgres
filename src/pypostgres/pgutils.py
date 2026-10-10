from logging import getLogger
from typing import Any

from psycopg2 import sql

from .models import PGColumn, PGTable

logger = getLogger(__name__)


def _full_data_type(col: dict) -> str:
    """Rebuild a full SQL type from information_schema column attributes.

    information_schema.columns.data_type drops type modifiers (e.g. 'character
    varying' loses the '(10)'). Recombine length / precision / scale so that
    varchar(10) propagates identically to the source definition.
    """
    data_type = col.get("data_type")
    if data_type in ("character varying", "character") and col.get("character_maximum_length"):
        return f"{data_type}({col['character_maximum_length']})"
    if data_type == "numeric" and col.get("numeric_precision") is not None and col.get("numeric_scale") is not None:
        return f"{data_type}({col['numeric_precision']},{col['numeric_scale']})"
    if data_type in ("timestamp without time zone", "timestamp with time zone", "time without time zone", "time with time zone") and col.get("datetime_precision") is not None and col["datetime_precision"] > 0:
        return f"{data_type}({col['datetime_precision']})"
    return data_type


class PGUtils:
    tables: dict[str, PGTable] = {}

    def __init__(self, cur):
        if not cur:
            raise ValueError("Database cursor cannot be None")
        self.cur = cur

    def _check(self):
        if not self.cur:
            raise ValueError("Database cursor cannot be None")

    def get_replication_slot_lag(self, slot_name: str) -> int:
        self.cur.execute(
            """SELECT redo_lsn-restart_lsn AS lag
            FROM pg_control_checkpoint(), pg_replication_slots WHERE slot_name = %s""",
            (slot_name,),
        )
        slot_lag_bytes = self.cur.fetchone()["lag"]
        return slot_lag_bytes

    # Get a list of all tables in schema historical
    def get_table_list(self, schema_name="public") -> Any:
        self.cur.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = %s order by 1,2", (schema_name,))
        # How to convert RealDict to Json
        return self.cur.fetchall()

    def get_table_schema(self, table_name, schema_name="public") -> PGTable:
        self.cur.execute(
            """SELECT ordinal_position, column_name as name, data_type,
                      character_maximum_length, numeric_precision, numeric_scale, datetime_precision
               FROM information_schema.columns
               WHERE table_schema = %s AND table_name = %s
               ORDER BY ordinal_position""",
            (schema_name, table_name),
        )
        pgcolumns = []
        for k in self.cur.fetchall():
            col = dict(k)
            col["data_type"] = _full_data_type(col)
            for extra in ("character_maximum_length", "numeric_precision", "numeric_scale", "datetime_precision"):
                col.pop(extra, None)
            pgcolumns.append(PGColumn(**col))
        self.tables[f"{schema_name}.{table_name}"] = PGTable(name=table_name, schema=schema_name, column=pgcolumns)
        return self.tables[f"{schema_name}.{table_name}"]

    def exists_table(self, table_name, schema_name="public") -> bool:
        """
        Check if a table exists in the database.
        Args:
            table_name: Name of the table
            schema_name: Name of the schema (default: public)
            cursor: Optional cursor object to execute the query, so that it can reuse the same cursor
        Returns:
            True if the table exists, False otherwise
        """

        self.cur.execute("SELECT True FROM information_schema.tables WHERE table_schema = %s AND table_name = %s", (schema_name, table_name))
        r = self.cur.fetchone() or False

        return bool(r)

    def pg_settings(self, setting_name: str = "") -> dict | str | None:
        """
        Get PostgreSQL settings.
        If setting_name is provided, return the value of that setting.
        If not, return all settings as a dictionary.
        """
        if setting_name:
            self.cur.execute("SELECT setting FROM pg_settings WHERE name = %s", (setting_name,))
            return self.cur.fetchone()["setting"] if self.cur.rowcount > 0 else None
        else:
            self.cur.execute("SELECT name, setting FROM pg_settings")
            return {row["name"]: row["setting"] for row in self.cur.fetchall()}

    def get_foreign_keys(self, table_name: str, schema_name: str = "public") -> list[dict]:
        """
        Get foreign keys for a given table.
        Args:
            table_name: Name of the table
            schema_name: Name of the schema (default: public)
        Returns:
            List of foreign key dictionaries with constraint and column details.
        """
        if not table_name:
            raise ValueError("Table name cannot be empty")

        query = sql.SQL("""
            SELECT con.conname AS fk_constraint_name,
                   child_col.attname AS referencing_column_name,
                   child_ns.nspname AS referencing_table_schema,
                   child_tbl.relname AS referencing_table_name,
                   parent_col.attname AS referenced_column_name,
                   parent_ns.nspname AS referenced_table_schema,
                   parent_tbl.relname AS referenced_table_name
            FROM pg_catalog.pg_constraint con
            JOIN pg_catalog.pg_class parent_tbl ON con.confrelid = parent_tbl.oid
            JOIN pg_catalog.pg_attribute parent_col ON parent_col.attrelid = parent_tbl.oid AND parent_col.attnum = con.confkey[1]
            JOIN pg_catalog.pg_namespace parent_ns ON parent_tbl.relnamespace = parent_ns.oid
            JOIN pg_catalog.pg_class child_tbl ON con.conrelid = child_tbl.oid
            JOIN pg_catalog.pg_attribute child_col ON child_col.attrelid = child_tbl.oid AND child_col.attnum = con.conkey[1]
            JOIN pg_catalog.pg_namespace child_ns ON child_tbl.relnamespace = child_ns.oid
            WHERE con.contype = 'f'
            AND parent_tbl.relname = %s
            AND parent_ns.nspname = %s
        """)
        self.cur.execute(query, (table_name, schema_name))
        return self.cur.fetchall()

    def create_temporary_table(self, table_name, columns, on_commit="DELETE ROWS"):
        """
        Create a temporary table for archiving
        Args:
            table_name: Name of the temporary table
            columns: Dictionary of column names and types
            on_commit: Action to take on commit (default: DELETE ROWS)
        """
        col_defs = sql.SQL(", ").join(
            sql.SQL("{} {}").format(sql.Identifier(col), sql.SQL(dtype)) for col, dtype in columns.items()
        )
        query = sql.SQL("CREATE TEMPORARY TABLE IF NOT EXISTS {} ({}) ON COMMIT {}").format(
            sql.Identifier(table_name), col_defs, sql.SQL(on_commit)
        )
        self.cur.execute(query)
