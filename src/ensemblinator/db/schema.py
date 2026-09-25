import logging
import sys
from importlib.resources import files

from ensemblinator.db.connection import ConnectionProvider

_logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 1

SQL = files("ensemblinator.db.sql")

SCHEMA = SQL.joinpath("schema.sql").read_text()


class _SchemaOwner(ConnectionProvider):
    def _initialize_schema(self):
        version = self._connection().execute("PRAGMA user_version").fetchone()[0]

        if version == 0:
            self._create_schema()
        elif version < CURRENT_SCHEMA_VERSION:
            _logger.error("Database migration not implemented yet")
            sys.exit(1)
        elif version > CURRENT_SCHEMA_VERSION:
            _logger.error(
                f"Database schema version {version} is newer than the current version {CURRENT_SCHEMA_VERSION}"
            )
            sys.exit(1)

    def _create_schema(self):
        self._connection().executescript(SCHEMA)
        self._connection().execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        self._connection().commit()
