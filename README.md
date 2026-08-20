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

# Connect (dict-style cursor by default)
conn = pg.connect("host=localhost dbname=mydb user=myuser")
cur = conn.cursor()

# Query with dict-style access
cur.execute("SELECT * FROM users WHERE active = %s", (True,))
for row in cur.fetchall():
    print(row["name"], row["created_at"])

# Export to CSV
cur.execute("SELECT * FROM users")
cur.to_csv("users.csv")          # to a file
csv_text = cur.to_csv()          # or to a StringIO buffer
```

### Inspector — introspect the database

```python
db = pg.Inspector(conn).inspect()
db.print_all()                                   # pretty-print the tree
for schema in db.schemas:
    for table in schema.pgtable:
        print(table.name, table.indexes, table.partition)
```

### PGUtils — schema helpers

```python
utils = pg.utils(conn.cursor())
tables = utils.get_table_list(schema_name="public")
schema = utils.get_table_schema("users", schema_name="public")  # full column types, e.g. varchar(10)
utils.exists_table("users")
utils.get_foreign_keys("orders")
utils.pg_settings("server_version")
```


## Tests

```sh
uv run pytest
```

Integration tests need a running PostgreSQL instance (see `Makefile` → `make tests`).