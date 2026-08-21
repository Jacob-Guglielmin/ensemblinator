from cli import job_state

import sys

COMMANDS = {
    "job-state": job_state.main
}

def main():
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
