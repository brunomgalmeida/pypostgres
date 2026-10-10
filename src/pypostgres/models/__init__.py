import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from datetime import timedelta as datetime_timedelta
from typing import List


# @dataclass
class Base:
    uuid: str
    name: str
    pg_oid: int
    # schema: str = "public"


@dataclass
class PGColumn(Base):
    name: str
    data_type: str
    ordinal_position: int = 0


@dataclass
class PGIndex(Base):
    """
    Represents a PostgreSQL index.

    Attributes:
        name (str): The name of the index.
        definition (str): The SQL definition of the index.
    """

    name: str
    definition: str

    def __post_init__(self):
        if not self.name:
            raise ValueError("Index name cannot be empty")
        if not self.definition:
            raise ValueError("Index definition cannot be empty")


@dataclass
class PGTable(Base):
    """
    Represents a PostgreSQL table.

    Attributes:
        name (str): The name of the table.
        schema (str): The schema of the table.
        columns (list[PGColumn]): List of columns in the table.
    """

    name: str
    schema: str
    column: List[PGColumn] = field(default_factory=list)  # List of columns in the table
    partition: list["PGPartition"] = field(default_factory=list)  # Dictionary to hold partition information
    parent: "PGTable | None" = None  # Reference to the parent table if this is a partitioned table
    indexes: List[PGIndex] = field(default_factory=list)  # List of indexes associated with the table

    def __post_init__(self):
        if not self.name:
            raise ValueError("Table name cannot be empty")
        if not self.schema:
            raise ValueError("Schema name cannot be empty")
        if not isinstance(self.column, list):
            raise TypeError("Column must be a list of PGColumn instances")
        if not all(isinstance(col, PGColumn) for col in self.column):
            raise TypeError("All items in column must be instances of PGColumn")

    def __repr__(self) -> str:
        output = f"PGTable(name={self.name}, schema={self.schema}, columns={len(self.column)}"
        if self.partition:
            output += f", partitions={len(self.partition)}"
        if self.indexes:
            output += f", indexes={len(self.indexes)}"
        if self.parent:
            output += f", parent={self.parent}"
        output += ")"

        return output


@dataclass
# TODO: this should extend PGTable
class PGPartition:
    """
    Represents a PostgreSQL partitioned table.
    """

    # def __init__(self, pgtable: PGTable, partition_expression: str = ""):
    pgtable: PGTable  # ?? or do we want to store the name and schema?
    expression: str
    default: bool = False  # Indicates if this is the default partition
    range: list[str | datetime] = field(default_factory=list)  # List to hold range values for partitioning

    name: str = None
    schema: str = None

    def __post_init__(self) -> None:
        if not isinstance(self.pgtable, PGTable):
            raise TypeError("pgtable must be an instance of PGTable")
        if not isinstance(self.expression, str):
            raise TypeError("expression must be a string")

        self.name = self.pgtable.name
        self.schema = self.pgtable.schema

        if not self.expression:
            self._type = "inheritance"
        else:
            self._type = "declarative"

            if self.expression == "DEFAULT":
                self.default = True

            elif "FOR VALUES WITH" in self.expression:
                # This regex will match: FOR VALUES WITH (modulus 16, remainder 0)
                match = re.search(r"FOR VALUES WITH\s*\((.*),\s*(.*?)\)", self.expression)
                if not match:
                    raise ValueError("Invalid partition expression format: " + self.expression)
                self.range.append(match[1])
                self.range.append(match[2])

            elif "FOR VALUES IN" in self.expression:
                # This regex will match: FOR VALUES IN ('EU', 'UK', 'DACH')
                match = re.search(r"FOR VALUES IN\s*\((.*?)\)", self.expression)
                if not match:
                    raise ValueError("Invalid partition expression format: " + self.expression)
                self.range = re.findall(r"'([^']*)'", match[1])

            elif "FOR VALUES FROM" in self.expression:
                # This regex will match "FOR VALUES FROM ('2025-07-01 00:00:00+00') TO ('2025-07-02 00:00:00+00')"
                # and multi-column keys like "FOR VALUES FROM ('web01', '2026-01-01') TO ('web01', '2027-01-01')"
                match = re.search(r"FOR VALUES FROM\s*\((.*?)\)\s*TO\s*\((.*?)\)", self.expression)
                if not match:
                    raise ValueError("Invalid partition expression format: " + self.expression)

                start = match[1]
                end = match[2]

                # Multi-column partition key (comma-separated values)
                if "," in start:
                    self.range.append([v.strip().strip("'") for v in start.split(",")])
                    self.range.append([v.strip().strip("'") for v in end.split(",")])
                elif "+" in start:
                    start = (start.replace("'", "") + "00").replace("+", " +")
                    end = (end.replace("'", "") + "00").replace("+", " +")
                    # Handle timezone-aware datetime
                    self.range.append(datetime.strptime(start, "%Y-%m-%d %H:%M:%S %z"))
                    self.range.append(datetime.strptime(end, "%Y-%m-%d %H:%M:%S %z"))
                else:
                    # Handle naive datetime
                    start = start.replace("'", "")
                    end = end.replace("'", "")
                    start_fmt = "%Y-%m-%d %H:%M:%S" if " " in start else "%Y-%m-%d"
                    end_fmt = "%Y-%m-%d %H:%M:%S" if " " in end else "%Y-%m-%d"
                    self.range.append(datetime.strptime(start, start_fmt))
                    self.range.append(datetime.strptime(end, end_fmt))

            else:
                raise ValueError("Unknown partition expression format: " + self.expression)

    def __repr__(self) -> str:
        return f"PGPartition({self.pgtable}, range={self.range}, default={self.default})"


def create_partitions_monthly(start_date: datetime, end_date: datetime, parent: PGTable, tz: str = "+0000") -> List[str]:
    """
    Create monthly partitions for a given table from start_date to end_date.
    Args:
        start_date (datetime): The start date for partitioning.
        end_date (datetime): The end date for partitioning.
        parent (PGTable): The parent table for which partitions are to be created.
        tz (str): Timezone string to be used in the partition names.
    Returns:
        None if cur is provided and SQL commands are executed, otherwise a list of SQL statements.
    """
    if not isinstance(start_date, datetime) or not isinstance(end_date, datetime):
        raise TypeError("start_date and end_date must be datetime objects")

    if not isinstance(parent, PGTable):
        raise TypeError("parent must be an instance of PGTable")

    output = []
    if start_date >= end_date:
        logging.error(f"Start date {start_date} is not before end date {end_date}. No partitions created.")
        return []

    parent_name = f"{parent.schema}.{parent.name}"
    no_months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month
    logging.debug(f"Creating {no_months} partitions for '{parent_name}' up to '{end_date}'")

    partition_end_date = start_date
    for i in range(1, no_months + 1):
        partition_start_date = partition_end_date
        partition_end_date = partition_start_date + datetime_timedelta(days=31)

        if partition_start_date >= end_date:
            logging.error(f"?? {partition_end_date=}")
            return []

        partition_name = f"{parent_name}_" + partition_start_date.strftime("%Y%m")
        month_start = partition_start_date.strftime("%Y-%m-01 00:00:00 " + tz)
        month_end = partition_end_date.strftime("%Y-%m-01 00:00:00 " + tz)

        sql = f"CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF {parent_name} FOR VALUES FROM ('{month_start}') TO ('{month_end}');"
        output.append(sql)

    return output


@dataclass
class PGForeignKey(Base):
    """
    Class to represent a PostgreSQL foreign key constraint.
    """

    name: str
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
class PGSchema(Base):
    """
    Represents a PostgreSQL schema.

    Attributes:
        name (str): The name of the schema.
    """

    name: str
    pgtable: List[PGTable] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Schema name cannot be empty")


@dataclass
class PGExtension(Base):
    """
    Represents an installed PostgreSQL extension.

    Attributes:
        name (str): The name of the extension.
        version (str): The installed version of the extension.
    """

    name: str
    version: str

    def __post_init__(self):
        if not self.name:
            raise ValueError("Extension name cannot be empty")
        if not self.version:
            raise ValueError("Extension version cannot be empty")


@dataclass
class PGDatabase(Base):
    """
    Represents a PostgreSQL database.

    Attributes:
        name (str): The name of the database.
    """

    name: str
    schemas: List[PGSchema] = field(default_factory=list)
    tables: dict[tuple[str, str], PGTable] = field(default_factory=dict)  # Dictionary to hold tables for quick access
    indexes: dict[tuple[str, str], PGIndex] = field(default_factory=dict)  # Dictionary to hold indexes for quick access
    extensions: List[PGExtension] = field(default_factory=list)  # List of installed extensions

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Database name cannot be empty")

    def print_all(self, show_columns=True, show_partitions=True, show_children=True, show_indexes=False) -> None:
        """
        Print all schemas and their tables in the database.
        """
        for schema in self.schemas:
            print(f"Schema: {schema.name}")
            for table in schema.pgtable:
                if table.parent and not show_children:
                    continue

                print(f"  Table: {table}")

                if show_columns:
                    print("    Columns:")
                    for column in table.column:
                        print(f"      - Column: {column.name} {column.data_type}")

                if show_indexes:
                    print("    Indexes:")
                    for index in table.indexes:
                        print(f"      - Index: {index.name}")

                if show_partitions:
                    if table.partition:
                        print(f"    Partitions: [{len(table.partition)}]")
                        for partition in table.partition:
                            print(f"      - Partition: {partition.pgtable.name} [{partition.expression}]")
                            for index in partition.pgtable.indexes:
                                print(f"         - Index:  {index.name}")
