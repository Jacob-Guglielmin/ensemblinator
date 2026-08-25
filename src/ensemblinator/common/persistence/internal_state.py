from ensemblinator.common.persistence import kv_store
from ensemblinator.common import common

from pathlib import Path

_DB_FILENAME = "ensemblinator-state.sqlite3"

def state_get(state_dir: Path, job_id: str, key: str): return kv_store.kv_get(state_dir / _DB_FILENAME, job_id, key)
def state_set(state_dir: Path, job_id: str, key: str, value: str): return kv_store.kv_set(state_dir / _DB_FILENAME, job_id, key, value)
