# Notes

```py
def get_foreign_keys(cur, table_name, column_name="id", schema_name="public"):
    """
    Get foreign keys for a given table
    Args:
        table_name: Name of the table
    Returns:
        List of foreign keys
    """
    if not cur:
        raise ValueError("Database cursor cannot be None")
    if not table_name:
        raise ValueError("Table name cannot be empty")
    """
    SELECT
        conname AS constraint_name,
        pg_get_constraintdef(oid) AS constraint_definition
    FROM
        pg_catalog.pg_constraint
    WHERE
        contype = 'f'
        AND conrelid = 'public.nodes'::regclass;

    """
    cur.execute(f"""
        SELECT con.conname AS fk_constraint_name,
               child_tbl.relname AS referencing_table_name,
               child_col.attname AS referencing_column_name,
               child_ns.nspname AS referencing_table_schema
        FROM   pg_catalog.pg_constraint con
        JOIN   pg_catalog.pg_class parent_tbl ON con.confrelid = parent_tbl.oid
        JOIN   pg_catalog.pg_attribute parent_col ON parent_col.attrelid = parent_tbl.oid AND parent_col.attnum = con.confkey[1] -- Assuming 'id' is the first column in the FK
        JOIN   pg_catalog.pg_class child_tbl ON con.conrelid = child_tbl.oid
        JOIN   pg_catalog.pg_attribute child_col ON child_col.attrelid = child_tbl.oid AND child_col.attnum = con.conkey[1] -- Assuming the FK references a single 'id' column
        JOIN   pg_catalog.pg_namespace child_ns ON child_tbl.relnamespace = child_ns.oid
        WHERE con.contype = 'f'
        AND   parent_tbl.relname = '{table_name}'
        AND   parent_col.attname = '{column_name}'
    """)
    return cur.fetchall()
```
