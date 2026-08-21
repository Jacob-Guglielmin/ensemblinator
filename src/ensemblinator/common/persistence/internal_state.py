from ensemblinator.common.persistence import kv_store
from ensemblinator.common import common

_DB = common.STATE_DIR / "ensemblinator-state.sqlite3"

def state_get(job_id: str, key: str): return kv_store.kv_get(_DB, job_id, key)
def state_set(job_id: str, key: str, value: str): return kv_store.kv_set(_DB, job_id, key, value)
