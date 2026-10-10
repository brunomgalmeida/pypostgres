import importlib.metadata as importlib_metadata
from logging import getLogger
from select import select
from typing import Any

import psycopg2
import psycopg2.extensions as extensions
import psycopg2.extras as extras
from psycopg2 import OperationalError
from psycopg2._psycopg import connection, cursor

from .inspector import Inspector
from .models import PGColumn, PGDatabase, PGExtension, PGForeignKey, PGIndex, PGPartition, PGSchema, PGTable
from .PGCustomCursor import CustomCursor
from .pgutils import PGUtils as utils

# from .pgutils import get_foreign_keys

logger = getLogger(__name__)

__version__ = importlib_metadata.version(__package__ or __name__)


# _Connection: TypeAlias = connection
def wait_select_inter(conn) -> None:
    """
    Allows the connection to be terminated at any point with a ctrl+c (KeyboardInterrupt).
    This is useful for long-running queries or operations that may need to be interrupted.
    This function is a callback for psycopg2's set_wait_callback.
    """
    while 1:
        try:
            state = conn.poll()
            if state == extensions.POLL_OK:
                break
            elif state == extensions.POLL_READ:
                select([conn.fileno()], [], [])
            elif state == extensions.POLL_WRITE:
                select([], [conn.fileno()], [])
            else:
                raise OperationalError("bad state from poll: %s" % state)
        except KeyboardInterrupt:
            conn.cancel()
            continue


# Register the wait callback to allow for KeyboardInterrupt handling
extensions.set_wait_callback(wait_select_inter)

# ++ https://stackoverflow.com/questions/31796332/psycopg2-insert-python-dictionary-as-json
# ** It allows you to use Python dictionaries directly in your SQL queries.
extensions.register_adapter(dict, extras.Json)


# !! TODO: Enforce application_name???
def connect(
    dsn: str | None = None,
    connection_factory: connection | None = None,
    cursor_factory: connection | cursor | None = None,
    **kwargs: Any,
) -> connection:
    """
    Create a new database connection.
    """
    # psycopg2.extensions.Cursor
    # https://www.postgresql.org/docs/current/libpq-envars.html
    # Export PG env variables from the config if exists
    # # If the config has a key called "hostname", replace it with "host"
    # if config.get("hostname"):
    #     config["host"] = config.pop("hostname")
    # for k, v in config.items():
    #     if k.startswith(envvar_prefix):
    #         os.environ[k.replace(envvar_prefix, "")] = v
    # logger.debug("mycustom conn")
    cursor_factory = cursor_factory or CustomCursor or extras.RealDictCursor  # type: ignore
    return psycopg2.connect(
        dsn=dsn,
        connection_factory=connection_factory,
        cursor_factory=cursor_factory,
        **kwargs,
    )
