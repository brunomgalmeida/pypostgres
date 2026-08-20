import csv
from io import StringIO
from logging import getLogger

import psycopg2.extras as extras

logger = getLogger(__name__)


class CustomCursor(extras.RealDictCursor):
    """
    A cursor class that uses RealDictCursor as default.
    """

    def __init__(self, *args, **kwargs):
        # logger.debug("mycustom cursor")
        super().__init__(*args, **kwargs)

    def to_csv(self, filename: str = None, delimiter: str = ",", fetchsize=100, **kwargs) -> None:
        """
        Export the cursor to a CSV file.
        """
        logger.debug(f"Exporting {__name__} to {filename} with delimiter {delimiter} and options {kwargs}")

        if not self.query:
            logger.debug("No query to export")
            return

        resultset = self.fetchone()
        logger.debug("Got 1 row")

        if not (resultset) or len(resultset) == 0:
            logger.debug("No data to dump")
            return

        # !! cur.rowcount, cur.statusmessage, cur.description are are only updated after a fetchall
        # logging.debug(f"resultset contains {cur.rowcount} rows, statusmessage={cur.statusmessage}")
        # header = [desc[0] for desc in self.description]

        header = resultset.keys()
        logger.debug(f"Header: {header}")

        if not filename:
            csvfile = StringIO()
        else:
            csvfile = open(filename, "w")

        writer = csv.DictWriter(csvfile, fieldnames=header, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerow(resultset)
        while len(resultset) > 0:
            resultset = self.fetchmany(fetchsize)
            logger.debug(f"Got {len(resultset)} rows")
            writer.writerows(resultset)
        if not filename:
            csvfile.seek(0)
            return csvfile
        else:
            csvfile.close()
            logger.debug(f"Exported to {filename}")
            return filename

    # TODO: add to_parquet, to_json, to_excel, to_sql, to_dict, to_list, to_dataframe, etc.
