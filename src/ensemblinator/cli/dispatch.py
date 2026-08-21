from ensemblinator.cli import job_state

import sys
import os

COMMANDS = {
    "job-state": job_state.main
}

def main():
    job_id = os.environ.get("JOB_ID")
    if job_id is None:
        # TODO entry point to make this possible with ensemblinator cli
        print("[ensemblinator-tools]: JOB_ID not set (are you running a job file manually?)", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("usage: ensemblinator-tools <command> [args...]", file=sys.stderr)
        print(f"commands: {", ".join(COMMANDS)}", file=sys.stderr)
        sys.exit(1)

    # fix the args for downstream parsers
    command, *rest = sys.argv[1:]
    sys.argv = [command, *rest]

    COMMANDS[command]()

if __name__ == "__main__":
    main()
