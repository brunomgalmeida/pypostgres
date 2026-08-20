from dataclasses import dataclass

from psycopg2 import sql


# @dataclass
class PGObject:
    """
    Class to represent a PostgreSQL object (table, view, index, etc.)
    """

    def __init__(self, schema: str, name: str, type: str) -> None:
        self.schema = schema
        self.name = name
        self.type = type
        self.oid = None  # OID of the object, can be set later
        self.full_name = f"{self.schema}.{self.name}"


@dataclass
class PGColumn:
    ordinal_position: int
    column_name: str
    data_type: str
    # data_pgtype: int
    # default: str = ""

    def __eq__(self, other):
        return self.ordinal_position == other.ordinal_position and self.column_name == other.column_name and self.data_type == other.data_type

    def __str__(self):
        return f"{self.column_name} ({self.data_type})"

    def __repr__(self):
        return f"PGColumn(column_name='{self.column_name}', data_type='{self.data_type}')"

    def sql(self) -> str:
        """
        Generate SQL statement to create the column.
        Returns:
            SQL statement as a string.
        """
        return f"{self.column_name} {self.data_type}"


@dataclass
class PGIndex:
    indexdef: str
    table_name: str = None
    indexname: str = None

    def __post_init__(self):
        if not self.indexname:
            raise ValueError("Index name cannot be empty")

    def __str__(self):
        return f"{self.indexname} on {self.table_name} ({'unique' if self.is_unique else 'non-unique'})"

    def __repr__(self):
        return f"PGIndex(name={self.indexname}, indexdef={self.indexdef})"

    def sql(self) -> str:
        """
        Generate SQL statement to create the index.
        Returns:
            SQL statement as a string.
        """
        return f"CREATE INDEX {self.indexname} ON {self.table_name} {self.indexdef};"

    def __eq__(self, value):
        if not isinstance(value, PGIndex):
            return False
        return self.indexname == value.indexname and self.indexdef == value.indexdef and self.table_name == value.table_name


@dataclass
class PGForeignKey:
    """
    Class to represent a PostgreSQL foreign key constraint.
    """

    table_name: str
    column_name: str
    foreign_table_name: str
    foreign_column_name: str
    # constraint_name: str | None = None

    def __str__(self):
        return f"{self.table_name}.{self.column_name} -> {self.foreign_table_name}.{self.foreign_column_name}"

    def __repr__(self):
        return f"PGForeignKey({self.table_name}, {self.column_name}, {self.foreign_table_name}, {self.foreign_column_name})"

    def __eq__(self, other):
        if not isinstance(other, PGForeignKey):
            return False
        return (
            self.table_name == other.table_name
            and self.column_name == other.column_name
            and self.foreign_table_name == other.foreign_table_name
            and self.foreign_column_name == other.foreign_column_name
        )

    def sql(self) -> str:
        """
        Generate SQL statement to create the foreign key constraint.
        Returns:
            SQL statement as a string.
        """
        return f"ALTER TABLE {self.table_name} ADD CONSTRAINT fk_{self.column_name} FOREIGN KEY ({self.column_name}) REFERENCES {self.foreign_table_name}({self.foreign_column_name});"


@dataclass
class PGPartitionRange:
    value_from: str  # Start of the partition range
    value_to: str  # End of the partition range
    subpartition: str  #


@dataclass
class PGPartitionChild:
    # Partition of: account_statements FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2025-02-01 00:00:00+00')
    name: str  # Name of the partition table
    schema: str
    # parent: str
    # parent_schema: str  # Schema of the parent table
    partition_expression: str  # Partition expression, e.g., "FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2025-02-01 00:00:00+00')"


@dataclass
class PGPartition:
    parent: str  # Parent table name
    children: list  # List of PGPartitionChild tables

    # Return a len of the children
    def __len__(self):
        return len(self.children)

    def __str__(self):
        return f"PGPartition(parent={self.parent}, children={self.children})"


@dataclass
class PGTable:
    name: str
    columns: list = None  # <PGColumn>
    indexes: list = None  # <PGIndex>
    fkeys: list = None  # <PGForeignKey>
    full_name: str = None  # Full name of the table in the format schema.table_name
    schema: str = "public"
    partitions: PGPartition = None  # List of PGPartition objects representing partitioned tables
    # TABLESPACE
    #  table_catalog | table_schema |  table_name  | table_type | self_referencing_column_name | reference_generation | user_defined_type_catalog | user_defined_type_schema | user_defined_type_name | is_insertable_into | is_typed | commit_action

    def __post_init__(self):
        self.full_name = f"{self.schema}.{self.name}"

    def __eq__(self, other):
        """Compare with another PGTable and return diferences"""
        pass

    def get_all_metadata(self, cur):
        """
        Get all metadata for the table.
        Args:
            cur: Database cursor
        Returns:
            List of PGColumn objects representing the columns in the table.
        """
        cur.execute(sql.SQL("""
            SELECT ordinal_position, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = {} AND table_name = {}
            ORDER BY ordinal_position
        """).format(sql.Identifier(self.schema), sql.Identifier(self.name)))
        rows = cur.fetchall()
        self.columns = [PGColumn(**row) for row in rows]

        # Get all the indexes for the table
        cur.execute(sql.SQL("""
            SELECT indexname, substring (indexdef, '\\(.*\\)') as indexdef
            FROM pg_indexes
            WHERE schemaname = {} AND tablename = {}
        """).format(sql.Identifier(self.schema), sql.Identifier(self.name)))
        rows = cur.fetchall()
        self.indexes = [PGIndex(**row) for row in rows]

        # Get all parent and child tables if this is an inheritance table
        inheritance = dba.get_inheritance(cur, self.name, self.schema)
        if inheritance:
            self.partitions = PGPartition(parent=self.name, children=inheritance)
        else:
            self.partitions = None

        return self.columns

    def __str__(self):
        return f"PGTable(name={self.name}, schema={self.schema}, columns={len(self.columns)}, indexes={len(self.indexes) if self.indexes else 0})"

    def sql(self, table: bool = True, indexes: bool = False, foreign_keys: bool = False) -> str:
        """
        Generate SQL statement to create the table.
        Returns:
            SQL statements as a string.
        """

        sql = ""
        if table:
            column_definitions = ", ".join([f"{col.column_name} {col.data_type}" for col in self.columns])
            sql += f"CREATE TABLE {self.full_name} ({column_definitions});"

        if indexes and self.indexes:
            for index in self.indexes:
                sql += index.sql() + "\n"

        if foreign_keys and self.fkeys:
            for fk in self.fkeys:
                sql += fk.sql() + "\n"

        return sql
