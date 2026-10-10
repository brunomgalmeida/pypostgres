from datetime import datetime

import pytest

from pypostgres.models import (
    PGColumn,
    PGDatabase,
    PGExtension,
    PGForeignKey,
    PGIndex,
    PGPartition,
    PGSchema,
    PGTable,
    create_partitions_monthly,
)


# == PGColumn ==

def test_pgcolumn_creation():
    col = PGColumn(name="id", data_type="integer", ordinal_position=1)
    assert col.name == "id"
    assert col.data_type == "integer"
    assert col.ordinal_position == 1


def test_pgcolumn_defaults():
    col = PGColumn(name="name", data_type="text")
    assert col.ordinal_position == 0


# == PGIndex ==

def test_pgindex_creation():
    idx = PGIndex(name="idx_users_email", definition="CREATE INDEX idx_users_email ON users (email)")
    assert idx.name == "idx_users_email"
    assert idx.definition == "CREATE INDEX idx_users_email ON users (email)"


def test_pgindex_empty_name_raises():
    with pytest.raises(ValueError, match="Index name cannot be empty"):
        PGIndex(name="", definition="CREATE INDEX idx ON t (c)")


def test_pgindex_empty_definition_raises():
    with pytest.raises(ValueError, match="Index definition cannot be empty"):
        PGIndex(name="idx", definition="")


# == PGExtension ==

def test_pgextension_creation():
    ext = PGExtension(name="plpgsql", version="1.6")
    assert ext.name == "plpgsql"
    assert ext.version == "1.6"


def test_pgextension_empty_name_raises():
    with pytest.raises(ValueError, match="Extension name cannot be empty"):
        PGExtension(name="", version="1.6")


def test_pgextension_empty_version_raises():
    with pytest.raises(ValueError, match="Extension version cannot be empty"):
        PGExtension(name="plpgsql", version="")


# == PGTable ==

def test_pgtable_creation():
    table = PGTable(name="users", schema="public")
    assert table.name == "users"
    assert table.schema == "public"
    assert table.column == []
    assert table.partition == []
    assert table.parent is None
    assert table.indexes == []


def test_pgtable_with_columns():
    cols = [
        PGColumn(name="id", data_type="integer", ordinal_position=1),
        PGColumn(name="name", data_type="text", ordinal_position=2),
    ]
    table = PGTable(name="users", schema="public", column=cols)
    assert len(table.column) == 2
    assert table.column[0].name == "id"


def test_pgtable_empty_name_raises():
    with pytest.raises(ValueError, match="Table name cannot be empty"):
        PGTable(name="", schema="public")


def test_pgtable_empty_schema_raises():
    with pytest.raises(ValueError, match="Schema name cannot be empty"):
        PGTable(name="users", schema="")


def test_pgtable_column_not_list_raises():
    with pytest.raises(TypeError, match="Column must be a list"):
        PGTable(name="users", schema="public", column="not_a_list")


def test_pgtable_column_wrong_type_raises():
    with pytest.raises(TypeError, match="All items in column must be instances of PGColumn"):
        PGTable(name="users", schema="public", column=["not_a_column"])


def test_pgtable_repr():
    table = PGTable(name="users", schema="public")
    r = repr(table)
    assert "users" in r
    assert "public" in r
    assert "columns=0" in r


def test_pgtable_repr_with_partitions():
    table = PGTable(name="events", schema="public")
    child = PGTable(name="events_202501", schema="public")
    part = PGPartition(pgtable=child, expression="FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2025-02-01 00:00:00+00')")
    table.partition.append(part)
    r = repr(table)
    assert "partitions=1" in r


# == PGPartition ==

def test_pgpartition_default_expression():
    child = PGTable(name="events_default", schema="public")
    part = PGPartition(pgtable=child, expression="DEFAULT")
    assert part.default is True
    assert part.name == "events_default"
    assert part.schema == "public"
    assert part.range == []


def test_pgpartition_range_from_to_naive():
    """Naive datetime parsing should strip quotes and parse."""
    child = PGTable(name="events_202501", schema="public")
    part = PGPartition(
        pgtable=child,
        expression="FOR VALUES FROM ('2025-01-01 00:00:00') TO ('2025-02-01 00:00:00')",
    )
    assert len(part.range) == 2
    assert part.range[0] == datetime(2025, 1, 1)
    assert part.range[1] == datetime(2025, 2, 1)
    assert part.range[0].tzinfo is None


def test_pgpartition_range_from_to_timezone():
    child = PGTable(name="events_202501tz", schema="public")
    part = PGPartition(
        pgtable=child,
        expression="FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2025-02-01 00:00:00+00')",
    )
    assert len(part.range) == 2
    assert part.range[0].tzinfo is not None
    assert part.range[1].tzinfo is not None


def test_pgpartition_hash_modulus():
    child = PGTable(name="events_mod", schema="public")
    part = PGPartition(
        pgtable=child,
        expression="FOR VALUES WITH (MODULUS 16, REMAINDER 0)",
    )
    assert len(part.range) == 2
    assert "MODULUS 16" in part.range[0]
    assert "REMAINDER 0" in part.range[1]


def test_pgpartition_list_in():
    child = PGTable(name="sales_emea", schema="public")
    part = PGPartition(
        pgtable=child,
        expression="FOR VALUES IN ('EU', 'UK', 'DACH')",
    )
    assert part.range == ["EU", "UK", "DACH"]


def test_pgpartition_range_multi_column():
    child = PGTable(name="metrics_web01", schema="public")
    part = PGPartition(
        pgtable=child,
        expression="FOR VALUES FROM ('web01', '2026-01-01 00:00:00') TO ('web01', '2027-01-01 00:00:00')",
    )
    assert len(part.range) == 2
    assert part.range[0] == ["web01", "2026-01-01 00:00:00"]
    assert part.range[1] == ["web01", "2027-01-01 00:00:00"]


def test_pgpartition_empty_expression_is_inheritance():
    child = PGTable(name="events_inh", schema="public")
    part = PGPartition(pgtable=child, expression="")
    assert part._type == "inheritance"
    assert part.range == []


def test_pgpartition_invalid_expression_raises():
    child = PGTable(name="events_bad", schema="public")
    with pytest.raises(ValueError, match="Unknown partition expression format"):
        PGPartition(pgtable=child, expression="INVALID EXPRESSION")


def test_pgpartition_invalid_from_to_raises():
    child = PGTable(name="events_bad2", schema="public")
    with pytest.raises(ValueError, match="Invalid partition expression format"):
        PGPartition(pgtable=child, expression="FOR VALUES FROM  TO")


def test_pgpartition_non_pgtable_raises():
    with pytest.raises(TypeError, match="pgtable must be an instance of PGTable"):
        PGPartition(pgtable="not_a_table", expression="DEFAULT")


def test_pgpartition_repr():
    child = PGTable(name="events_repr", schema="public")
    part = PGPartition(pgtable=child, expression="DEFAULT")
    r = repr(part)
    assert "events_repr" in r
    assert "default=True" in r


# == PGForeignKey ==

def test_pgforeignkey_creation():
    fk = PGForeignKey(
        name="fk_user",
        table_name="orders",
        column_name="user_id",
        foreign_table_name="users",
        foreign_column_name="id",
    )
    assert fk.table_name == "orders"
    assert fk.column_name == "user_id"
    assert fk.foreign_table_name == "users"
    assert fk.foreign_column_name == "id"


def test_pgforeignkey_str():
    fk = PGForeignKey(
        name="fk_user",
        table_name="orders",
        column_name="user_id",
        foreign_table_name="users",
        foreign_column_name="id",
    )
    s = str(fk)
    assert "orders" in s
    assert "users" in s


def test_pgforeignkey_eq():
    fk1 = PGForeignKey(name="fk", table_name="a", column_name="b", foreign_table_name="c", foreign_column_name="d")
    fk2 = PGForeignKey(name="fk", table_name="a", column_name="b", foreign_table_name="c", foreign_column_name="d")
    assert fk1 == fk2


def test_pgforeignkey_ne():
    fk1 = PGForeignKey(name="fk1", table_name="a", column_name="b", foreign_table_name="c", foreign_column_name="d")
    fk2 = PGForeignKey(name="fk2", table_name="x", column_name="y", foreign_table_name="z", foreign_column_name="w")
    assert fk1 != fk2


def test_pgforeignkey_ne_different_type():
    fk = PGForeignKey(name="fk", table_name="a", column_name="b", foreign_table_name="c", foreign_column_name="d")
    assert fk != "not_a_fk"


def test_pgforeignkey_sql():
    fk = PGForeignKey(
        name="fk_user",
        table_name="orders",
        column_name="user_id",
        foreign_table_name="users",
        foreign_column_name="id",
    )
    sql = fk.sql()
    assert "ALTER TABLE orders" in sql
    assert "REFERENCES users(id)" in sql


# == PGSchema ==

def test_pgschema_creation():
    schema = PGSchema(name="public")
    assert schema.name == "public"
    assert schema.pgtable == []


def test_pgschema_empty_name_raises():
    with pytest.raises(ValueError, match="Schema name cannot be empty"):
        PGSchema(name="")


# == PGDatabase ==

def test_pgdatabase_creation():
    db = PGDatabase(name="testdb")
    assert db.name == "testdb"
    assert db.schemas == []
    assert db.tables == {}
    assert db.indexes == {}


def test_pgdatabase_extensions_defaults_empty():
    db = PGDatabase(name="testdb")
    assert db.extensions == []


def test_pgdatabase_empty_name_raises():
    with pytest.raises(ValueError, match="Database name cannot be empty"):
        PGDatabase(name="")


def test_pgdatabase_print_all(capsys):
    schema = PGSchema(name="public")
    table = PGTable(name="users", schema="public", column=[PGColumn(name="id", data_type="integer")])
    schema.pgtable.append(table)
    db = PGDatabase(name="testdb", schemas=[schema])
    db.print_all()
    captured = capsys.readouterr()
    assert "public" in captured.out
    assert "users" in captured.out
    assert "id" in captured.out


def test_pgdatabase_print_all_no_children(capsys):
    parent = PGTable(name="events", schema="public")
    child = PGTable(name="events_202501", schema="public", parent=parent)
    schema = PGSchema(name="public")
    schema.pgtable.extend([parent, child])
    db = PGDatabase(name="testdb", schemas=[schema])
    db.print_all(show_children=False)
    captured = capsys.readouterr()
    assert "events_202501" not in captured.out


# == create_partitions_monthly ==

def test_create_partitions_monthly_basic():
    parent = PGTable(name="events", schema="public")
    start = datetime(2025, 1, 1)
    end = datetime(2025, 4, 1)
    result = create_partitions_monthly(start, end, parent)
    assert len(result) == 3
    assert "public.events_202501" in result[0]
    assert "public.events_202502" in result[1]
    assert "public.events_202503" in result[2]


def test_create_partitions_monthly_single_month():
    parent = PGTable(name="events", schema="public")
    start = datetime(2025, 1, 1)
    end = datetime(2025, 2, 1)
    result = create_partitions_monthly(start, end, parent)
    assert len(result) == 1


def test_create_partitions_monthly_start_after_end():
    parent = PGTable(name="events", schema="public")
    start = datetime(2025, 5, 1)
    end = datetime(2025, 1, 1)
    result = create_partitions_monthly(start, end, parent)
    assert result == []


def test_create_partitions_monthly_equal_dates():
    parent = PGTable(name="events", schema="public")
    start = datetime(2025, 1, 1)
    end = datetime(2025, 1, 1)
    result = create_partitions_monthly(start, end, parent)
    assert result == []


def test_create_partitions_monthly_custom_tz():
    parent = PGTable(name="events", schema="public")
    start = datetime(2025, 1, 1)
    end = datetime(2025, 2, 1)
    result = create_partitions_monthly(start, end, parent, tz="+0530")
    assert len(result) == 1
    assert "+0530" in result[0]


def test_create_partitions_monthly_sql_format():
    parent = PGTable(name="orders", schema="analytics")
    start = datetime(2025, 1, 1)
    end = datetime(2025, 2, 1)
    result = create_partitions_monthly(start, end, parent)
    assert "CREATE TABLE IF NOT EXISTS" in result[0]
    assert "PARTITION OF" in result[0]
    assert "FOR VALUES FROM" in result[0]


def test_create_partitions_monthly_invalid_start_date_type():
    parent = PGTable(name="events", schema="public")
    with pytest.raises(TypeError, match="start_date and end_date must be datetime objects"):
        create_partitions_monthly("2025-01-01", datetime(2025, 4, 1), parent)


def test_create_partitions_monthly_invalid_end_date_type():
    parent = PGTable(name="events", schema="public")
    with pytest.raises(TypeError, match="start_date and end_date must be datetime objects"):
        create_partitions_monthly(datetime(2025, 1, 1), "2025-04-01", parent)


def test_create_partitions_monthly_invalid_parent_type():
    with pytest.raises(TypeError, match="parent must be an instance of PGTable"):
        create_partitions_monthly(datetime(2025, 1, 1), datetime(2025, 4, 1), "not_a_table")
