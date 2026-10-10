# pypostgres tools

Standalone command-line tools built on top of the `pypostgres` library.

These consume the installed `pypostgres` package (the library lives under
`src/pypostgres/`). Each tool is both:

- runnable directly with `uv`: `uv run bin/<tool>.py ...`
- installable as a console command via `[project.scripts]` in `pyproject.toml`
  (after `uv pip install -e .`): `pypg-<tool> ...`

## Tools

### `schema-sync` — `pypg-schema-sync`

Compares column order and definitions across two PostgreSQL databases/schemas
and applies the differences from a **source** into a **destination** (one-way,
source → destination only).

The destination is mutated; the source connection is opened read-only.

#### Arguments

| Flag | Description |
| --- | --- |
| `--source` | JSON `{"uri": "<dsn>", "schema": "<schema>", "id": "<label>"}` for the source. |
| `--destination` | JSON `{"uri": "<dsn>", "schema": "<schema>", "id": "<label>"}` for the destination. |
| `--ignore-missing-tables` | Skip tables present in source but absent in destination (default: error). |
| `--dry-run` | Log the `ALTER` statements without committing them. |
| `-v`, `--verbose` | DEBUG-level logging to stdout. |

Logging verbosity can also be controlled with the `LOGLEVEL` environment
variable (defaults to `WARNING`).

#### Behavior

For each table in the source schema:

- Column **missing** in destination → emits
  `ALTER TABLE <schema>.<table> ADD COLUMN IF NOT EXISTS <name> <type>`.
- Column **type mismatch** → emits
  `ALTER TABLE <schema>.<table> ALTER COLUMN <name> SET DATA TYPE <type>`.
- Column **name mismatch** or **extra column** in destination → raises an
  exception (these are never auto-fixed).

#### Output

Logs are written to stdout. Unless `--dry-run` is set, the destination
transaction is committed after each table; the source transaction is always
cancelled.

#### Example

```sh
x="postgresql://user:pass@host:5432/mydb"
LOGLEVEL=WARNING pypg-schema-sync \
  --source      '{"uri": "'$x'", "schema": "public", "id":"source"}' \
  --destination '{"uri": "'$x'", "schema": "historical", "id":"destination"}' \
  --ignore-missing-tables
```
