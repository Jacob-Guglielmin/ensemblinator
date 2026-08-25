from ensemblinator.cli import job_state

import sys
import os

COMMANDS = {
    "job-state": job_state.main
}

def _require_env(var_name: str) -> str:
    value = os.environ.get(var_name)
    if value is None:
        print("[ensemblinator-tools]: missing required environment variables. job files should not be run manually.", file=sys.stderr)
        print("[ensemblinator-tools]: invoke a job file directly using `ensemblinator --config <path> --manual-job-run <path>", file=sys.stderr)
        sys.exit(1)
    return value

def main():
    expected_env_vars = ["JOB_ID", "STATE_DIR"]
    env_vars = {var_name.lower(): _require_env(var_name) for var_name in expected_env_vars}        

    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("usage: ensemblinator-tools <command> [args...]", file=sys.stderr)
        print(f"commands: {", ".join(COMMANDS)}", file=sys.stderr)
        sys.exit(1)

    # fix the args for downstream parsers
    command, *rest = sys.argv[1:]
    sys.argv = [command, *rest]

    COMMANDS[command](**env_vars)
