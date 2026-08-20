# pypostgres

A thin psycopg2 wrapper with a PostgreSQL metadata and introspection toolkit.

## Features

- `connect()` — wraps `psycopg2.connect()` with a dict-style cursor by default, sets a wait callback so Ctrl+C cancels in-flight queries, and registers a dict-to-JSON adapter.
- `CustomCursor` — dict-style cursor with a `to_csv(fileobj_or_path)` method that streams query results to CSV.
- `Inspector` — introspects a live database via `information_schema`, `pg_indexes`, and `pg_inherits` into a `PGDatabase` tree of typed dataclasses (`PGSchema` → `PGTable` → `PGColumn` / `PGIndex` / `PGPartition` / `PGForeignKey`). `db.print_all()` pretty-prints the tree.
- `utils` — helpers such as `get_replication_slot_lag()`, `get_table_list()`, `get_table_schema()`, `exists_table()`, `pg_settings()`, and `create_temporary_table()`.
- `create_partitions_monthly()` — backfills missing monthly partitions for a parent table.

## Requirements

- Python >= 3.8
- psycopg2-binary >= 2.9.10
- A running PostgreSQL server

## Install

```sh
uv sync
uv pip install -e .[dev]
```

## Quick usage

```python
import pypostgres as pg

conn = pg.connect("host=localhost dbname=mydb user=myuser")
cur = conn.cursor()

cur.execute("SELECT * FROM users WHERE active = %s", (True,))
row = cur.fetchone()
print(row["name"])  # dict-style access

cur.execute("SELECT * FROM users")
cur.to_csv("users.csv")

inspector = pg.Inspector(conn).inspect()
inspector.print_all()
```

## How the Inspector works

`Inspector.inspect()` builds an in-memory `PGDatabase` tree in three catalog passes, using psycopg2 `DictCursor` rows that map directly onto the dataclasses:

1. **Columns** — reads `information_schema.columns` and creates a `PGTable` per `(schema, table)`, appending a `PGColumn` for each column.
2. **Indexes** — reads `pg_indexes` and attaches a `PGIndex` to each table.
3. **Partitions** — reads `pg_inherits` + `pg_get_expr(relpartbound)` to link declarative partition children to their parent. Each partition's bound expression is parsed into a `PGPartition` supporting:
   - Range: `FOR VALUES FROM (...) TO (...)` (single-column, multi-column, naive and timezone-aware datetimes)
   - List: `FOR VALUES IN (...)`
   - Hash: `FOR VALUES WITH (MODULUS n, REMAINDER r)`
   - Default: `DEFAULT`
   - Empty expression = inheritance-based child (skipped with a warning, since these have no partition bound)

The result is navigable and printable:

```python
db = pg.Inspector(conn).inspect()
db.print_all(show_columns=False, show_partitions=False, show_children=False, show_indexes=False)
for schema in db.schemas:
    for table in schema.pgtable:
        print(table.name, table.indexes, table.partition)
```

## Tests

Integration tests require a running PostgreSQL instance. Run them with:

```sh
uv add --dev pytest
uv pip install -e .[dev]
uv run pytest -rP
```
