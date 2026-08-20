from logging import getLogger

import psycopg2
import psycopg2.extras

from .models import PGColumn, PGDatabase, PGIndex, PGPartition, PGSchema, PGTable

logger = getLogger(__name__)


# https://docs.sqlalchemy.org/en/20/core/inspection.html
# https://support.civisanalytics.com/hc/en-us/articles/360043041912-Direct-Database-Connections-via-SQLAlchemy-or-Psycopg2


class Inspector:
    """
    A class to inspect a PostgreSQL database and retrieve its structure.

    Attributes:
        conn: A psycopg2 connection object to the PostgreSQL database.
        db: An instance of PGDatabase that holds the database structure.
    """

    def __init__(self, conn) -> None:
        """
        Initialize the PGInspector with a database connection.
        Args:
            conn: A psycopg2 connection object to the PostgreSQL database.
        """
        if not conn:
            raise ValueError("Database connection cannot be None")
        self.conn = conn

    def inspect(self) -> PGDatabase:
        """
        Inspect the current database and print its structure.
        """
        filter_tables: str = "and table_name ilike 'account_statements%'"
        filter_schemas: str = "and table_schema not in ('information_schema', 'pg_catalog', 'pg_toast')"
        filter_tables = ""
        # filter_schemas = ""

        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # == Create a PGDatabase instance
        db: PGDatabase = PGDatabase(name="postgres")

        # == Create a db.tables dictionary for quick access
        db.tables = {}
        db.indexes = {}

        cur.execute(f"""
            SELECT table_schema, table_name, ordinal_position, column_name, data_type
            FROM information_schema.columns
            WHERE 1=1
            {filter_tables}
            {filter_schemas}
            ORDER BY table_schema, table_name, ordinal_position
        """)
        for entry in cur.fetchall():
            table_schema, table_name, ordinal_position, column_name, data_type = entry
            if (table_schema, table_name) not in db.tables:
                # Create a new PGTable instance if it doesn't exist
                logger.debug(f"Found table '{table_schema}.{table_name}'")
                db.tables[(table_schema, table_name)] = PGTable(name=table_name, schema=table_schema)

            # Add the column to the table's column list
            db.tables[(table_schema, table_name)].column.append(PGColumn(name=column_name, data_type=data_type, ordinal_position=ordinal_position))

        # !! Link things together, to avoid executing multiple queries to get all this information one by one

        # == Link indexes to tables
        # This will fetch all indexes in the database, excluding system schemas
        # and will link them to the corresponding tables in the db.tables dictionary.
        cur.execute(f"""
        with cte_indexes as (
            SELECT schemaname as table_schema, tablename as table_name, indexname, indexdef
            FROM pg_indexes
        )
        select *
        FROM   cte_indexes
        WHERE 1=1
        {filter_tables}
        {filter_schemas}
        ORDER BY 1,2,3,4
        """)
        indexes = cur.fetchall()
        for entry in indexes:
            table_schema, table_name, index_name, index_def = entry
            table: PGTable | None = db.tables.get((table_schema, table_name), None)
            logger.debug(f"Found index '{index_name}' on '{table_schema}.{table_name}'")
            if not table:
                logger.warning(f"Table {table_schema, table_name} not found. {index_name=}")
                continue  # Skip if the table is not found in the db.tables dictionary
            idx = PGIndex(name=index_name, definition=index_def)
            table.indexes.append(idx)
            db.indexes[(table_schema, index_name)] = idx

        # == Link Partitions
        cur.execute(f"""
        with cte_partitions as (
            SELECT  p.relnamespace::regnamespace             as table_schema,
                    p.relname                                as table_name,
                    c.relnamespace::regnamespace             as child_table_schema,
                    c.relname                                as child_table_name,
                    pg_get_expr(c.relpartbound, c.oid, true) as child_partition_expression
            FROM pg_inherits i
            JOIN pg_class c ON i.inhrelid = c.oid
            JOIN pg_class p ON i.inhparent = p.oid
            WHERE c.relkind = 'r'
        )
        SELECT *
        FROM  cte_partitions
        WHERE 1=1
        {filter_tables}
        {filter_schemas}
        ORDER BY 1,2,3,4
        """)

        partitions = cur.fetchall()

        for entry in partitions:
            parent_schema, parent_name, child_table_schema, child_table_name, partition_expression = entry
            if not partition_expression:
                logger.warning(f"Partition expression is empty for {parent_schema}.{parent_name} -> {child_table_schema}.{child_table_name}. Skipping.")
                continue

            # Find the schema and table to which this partition belongs
            logger.info(f"Found partition: {parent_schema}.{parent_name} -> {child_table_schema}.{child_table_name} with expression: {partition_expression}")

            table_parent: PGTable | None = db.tables.get((parent_schema, parent_name), None)
            if not table_parent:
                logger.warning(f"Table {parent_schema, parent_name} not found. {index_name=}")
                continue  # Skip if the table is not found in the db.tables dictionary

            # Get the child table and add it as a partition to the parent table
            child_table: PGTable | None = db.tables.get((child_table_schema, child_table_name), None)
            if not child_table:
                logger.warning(f"Child table {child_table_schema, child_table_name} not found. Skipping partition.")
                continue
            child_table.parent = table_parent  # Set the parent attribute of the child table
            table_parent.partition.append(PGPartition(pgtable=child_table, expression=partition_expression))

        # ** Convert the db.tables dictionary to a list of PGTable instances
        for (schema_name, table_name), pgtable in db.tables.items():
            # Check if the schema already exists in the database
            schema = next((s for s in db.schemas if s.name == schema_name), None)
            if not schema:
                # If the schema does not exist, create a new PGSchema instance
                logger.debug(f"Found schema '{schema_name}'")
                schema = PGSchema(name=schema_name)
                db.schemas.append(schema)

            # Add the table to the schema's pgtable list
            schema.pgtable.append(pgtable)

        return db


if __name__ == "__main__":
    # Example Usage 2
    import datetime
    import logging
    import os
    from typing import List

    import psycopg2

    def create_partitions_monthly(start_date, end_date, parent, tz="+0000") -> List[str]:
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
            partition_end_date = partition_start_date + datetime.timedelta(days=31)

            if partition_start_date >= end_date:
                logging.error(f"?? {partition_end_date=}")
                return []

            partition_name = f"{parent_name}_" + partition_start_date.strftime("%Y%m")
            month_start = partition_start_date.strftime("%Y-%m-01 00:00:00 " + tz)
            month_end = partition_end_date.strftime("%Y-%m-01 00:00:00 " + tz)

            sql = f"CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF {parent_name} FOR VALUES FROM ('{month_start}') TO ('{month_end}');"
            output.append(sql)

        return output

    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d: (%(name)s) %(lineno)d %(levelname)s: %(message)s",
        level=os.environ.get("LOGLEVEL", "DEBUG"),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    conn: psycopg2.extensions.connection = psycopg2.connect(
        "postgresql://localhost:5432/bet_whitelabel",
        password="xxxxxxxx",
        user="postgres",
        connect_timeout=30,
        client_encoding="utf8",
    )
    conn.autocommit = False
    # conn.set_isolation_level(0)  # Set isolation level to autocommit
    # conn.set_session(readonly=True)

    cur = conn.cursor()
    i = Inspector(conn)
    db = i.inspect()
    db.print_all(show_columns=False, show_partitions=False, show_children=False, show_indexes=False)

    partition_end_date = datetime.datetime.strptime("2030-02-01 00:00:00 +0000", "%Y-%m-%d %H:%M:%S %z")
    out: List[str] = []
    for t in db.tables:
        # print(f"Table: {t} -> {db.tables[t]}")
        if db.tables[t].partition:
            partition_max_date = datetime.datetime.strptime("2025-01-01 00:00:00 +0000", "%Y-%m-%d %H:%M:%S %z")

            logging.debug(f"Checking partitions for table {db.tables[t].name}")
            for p in db.tables[t].partition:
                if (not p.default) and (type(p._range[1]) is not datetime):
                    logging.warning("Partition %s has a non-datetime range end: %s", p.pgtable.name, p._range[1])
                    partition_max_date = None
                    continue

                if (not p.default) and (type(p._range[1]) is datetime) and p._range[1] > partition_max_date:
                    partition_max_date = p._range[1]

            logging.info(f"Last partition for {db.tables[t].name}: {partition_max_date}")

            if partition_max_date and partition_max_date < partition_end_date:
                logging.warning(f"Table {db.tables[t].name} '{partition_max_date}' is missing partitions up to '{partition_end_date}'")
                o = create_partitions_monthly(partition_max_date, partition_end_date, db.tables[t])
                if o:
                    out.extend(o)
                    logging.info(f"Created {len(o)} partitions for table {db.tables[t].name} up to {partition_end_date}.")
                else:
                    logging.error(f"Failed to create partitions for table {db.tables[t].name} up to {partition_end_date}.")

            else:
                logging.debug(f"Table {db.tables[t].name} has all partitions up to {partition_end_date}.")

        else:
            if db.tables[t].parent:
                continue
            logging.debug(f"Table {db.tables[t].name} has no partitions")

    if out:
        logging.info(f"Executing {len(out)} SQL statements to create partitions.")
        for sql in out:
            logging.debug(f"Executing SQL: {sql}")
            cur.execute(sql)

    conn.cancel()
