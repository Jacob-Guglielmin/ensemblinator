from ensemblinator.persistence import kv_store

import sys
import os
from pathlib import Path

USAGE = """usage: ensemblinator-tools job-state <get|set|delete> [args...]

  get <key>              print the value for <key> (empty string if unset)
  set <key> <value>      store <value> under <key>
  delete <key>           remove <key>
"""

def main(job_id: str, state_dir: str, **kwargs):
    db = Path(state_dir) / "job-state.sqlite3"

    args = sys.argv[1:]
    if not args:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    cmd, *rest = args

    try:
        if cmd == "get":
            if len(rest) != 1:
                print("[ensemblinator-tools job-state]: error: 'get' requires exactly one argument: <key>", file=sys.stderr)
                sys.exit(1)
            value = kv_store.kv_get(db, job_id, rest[0])
            print(value if value is not None else "", end="")

        elif cmd == "set":
            if len(rest) != 2:
                print("[ensemblinator-tools job-state]: error: 'set' requires exactly two arguments: <key> <value>", file=sys.stderr)
                sys.exit(1)
            kv_store.kv_set(db, job_id, rest[0], rest[1])

        elif cmd == "delete":
            if len(rest) != 1:
                print("[ensemblinator-tools job-state]: error: 'delete' requires exactly one argument: <key>", file=sys.stderr)
                sys.exit(1)
            kv_store.kv_delete(db, job_id, rest[0])

        else:
            print(f"[ensemblinator-tools job-state]: error: unknown command '{cmd}'", file=sys.stderr)
            print(USAGE, file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"[ensemblinator-tools job-state]: error: {e}", file=sys.stderr)
        sys.exit(1)
