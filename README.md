# pypostgres

A thin psycopg2 wrapper with a PostgreSQL metadata and introspection toolkit.

## Features

- `connect()` — dict-style cursor by default, Ctrl+C cancels in-flight queries, dict→JSON adapter.
- `CustomCursor` — dict-style cursor with `to_csv()` to stream results to a file or buffer.
- `Inspector` — introspects a live database into a `PGDatabase` tree (`PGSchema` → `PGTable` → `PGColumn`/`PGIndex`/`PGPartition`), including partitioned tables.
- `PGUtils` — table listing, schema inspection, existence checks, settings, foreign keys, temporary tables.
- `create_partitions_monthly()` — backfill missing monthly partitions.

## Install

### Install for Local development
```sh
uv sync
uv pip install -e .
```

### Install from GitHub

Install directly from a Git tag (no PyPI upload needed):

```sh
pip install "git+https://github.com/brunomgalmeida/pypostgres.git@v0.0.1"
# or with uv
uv add "git+https://github.com/brunomgalmeida/pypostgres.git@v0.0.1"
```

## Usage

```python
import pypostgres as pg

conn = pg.connect()
cur = conn.cursor()

# Query with dict-style access
cur.execute("SELECT id, name, email FROM customers ORDER BY id")
for row in cur.fetchall():
    print(row["id"], row["name"], row["email"])

# Export to CSV (into a StringIO buffer)
cur.execute("SELECT id, name, price FROM products ORDER BY id")
csv_text = cur.to_csv()
print(csv_text.getvalue())
```

```
1 Alice alice@example.com
2 Bob bob@example.com
3 Charlie charlie@example.com
id,name,price
1,Widget,9.99
2,Gadget,24.50
3,Doohickey,3.75
```

### Inspector — introspect the database

```python
db = pg.Inspector(conn).inspect()

# Print a summary of each top-level table
for schema in db.schemas:
    for table in schema.pgtable:
        if not table.parent:  # skip partition children
            print(f"{table.name}: {len(table.column)} cols, "
                  f"{len(table.indexes)} indexes, "
                  f"{len(table.partition)} partitions")
```

```
customers: 4 cols, 2 indexes, 0 partitions
events: 4 cols, 1 indexes, 7 partitions
events_detailed: 4 cols, 1 indexes, 0 partitions
events_detailed_2026_01: 4 cols, 1 indexes, 3 partitions
events_detailed_2026_02: 4 cols, 1 indexes, 3 partitions
logs: 3 cols, 0 indexes, 0 partitions
logs_2026_01: 3 cols, 1 indexes, 0 partitions
logs_2026_02: 3 cols, 1 indexes, 0 partitions
logs_2026_03: 3 cols, 1 indexes, 0 partitions
metrics: 4 cols, 0 indexes, 3 partitions
orders: 6 cols, 3 indexes, 0 partitions
products: 4 cols, 1 indexes, 0 partitions
sales: 5 cols, 1 indexes, 4 partitions
sessions: 5 cols, 1 indexes, 4 partitions
```

### PGUtils — schema helpers

```python
utils = pg.utils(conn.cursor())

# List tables in a schema
tables = utils.get_table_list(schema_name="public")
print(len(tables), "tables in public schema")

# Get full column types (e.g. varchar(10), numeric(10,2))
schema = utils.get_table_schema("orders", schema_name="public")
print(schema)

# Check if a table exists
print(utils.exists_table("orders"))

# Get foreign keys referencing a table
fks = utils.get_foreign_keys("customers")
for fk in fks:
    print(fk["referencing_table_name"], "->", fk["referenced_table_name"])

# Get server version
print(utils.pg_settings("server_version"))
```

```
38 tables in public schema
PGTable(name=orders, schema=public, columns=6)
True
orders -> customers
16.15 (Debian 16.15-1.pgdg13+2)
```

## Tools

Standalone command-line tools built on top of the library live in [`bin/`](./bin/).
See [`bin/README.md`](./bin/README.md) for the full list, arguments, and output
of each tool.

```sh
# Run a tool directly with uv
uv run bin/schema-sync.py --help

# Or install the console commands (pypg-schema-sync, ...)
uv pip install -e .
pypg-schema-sync --help
```

## Tests

```sh
uv run pytest
```

Integration tests need a running PostgreSQL instance (see `Makefile` → `make tests`).
