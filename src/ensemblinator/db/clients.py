from pathlib import Path

from ensemblinator.db.connection import _WithDBConnection
from ensemblinator.db.job_runs import _JobRunsMethods
from ensemblinator.db.job_state import _JobStateMethods
from ensemblinator.db.schema import _SchemaOwner


class Database(_WithDBConnection, _SchemaOwner, _JobRunsMethods):
    def __init__(self, state_directory: Path):
        super().__init__(state_directory)
        self._initialize_schema()


class JobStateClient(_WithDBConnection, _JobStateMethods):
    pass
