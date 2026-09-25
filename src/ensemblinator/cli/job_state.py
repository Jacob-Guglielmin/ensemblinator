import sys
from pathlib import Path

from ensemblinator.db.clients import JobStateClient

USAGE = """usage: ensemblinator-tools job-state <get|set|delete> [args...]

  get <key>              print the value for <key> (or exit code 1 if unset)
  set <key> <value>      store <value> under <key>
  delete <key>           remove <key>
"""


def main(job_id: str, state_dir: str, **kwargs):
    db = JobStateClient(Path(state_dir))

    args = sys.argv[1:]
    if not args:
        print(USAGE, file=sys.stderr)
        sys.exit(2)

    cmd, *rest = args

    try:
        if cmd == "get":
            if len(rest) != 1:
                print(
                    "[ensemblinator-tools job-state]: error: 'get' requires exactly one argument: <key>",
                    file=sys.stderr,
                )
                sys.exit(2)
            value = db.get_job_state(job_id, rest[0])
            if value is None:
                sys.exit(1)
            print(value, end="")

        elif cmd == "set":
            if len(rest) != 2:
                print(
                    "[ensemblinator-tools job-state]: error: 'set' requires exactly two arguments: <key> <value>",
                    file=sys.stderr,
                )
                sys.exit(2)
            db.set_job_state(job_id, rest[0], rest[1])

        elif cmd == "delete":
            if len(rest) != 1:
                print(
                    "[ensemblinator-tools job-state]: error: 'delete' requires exactly one argument: <key>",
                    file=sys.stderr,
                )
                sys.exit(2)
            db.delete_job_state(job_id, rest[0])

        else:
            print(
                f"[ensemblinator-tools job-state]: error: unknown command '{cmd}'", file=sys.stderr
            )
            print(USAGE, file=sys.stderr)
            sys.exit(2)

    except Exception as e:  # noqa: BLE001 - this is a CLI tool so a traceback should never be emitted
        print(f"[ensemblinator-tools job-state]: error: {e}", file=sys.stderr)
        sys.exit(2)

    finally:
        db.close()
