# CLI reference

ensemblinator comes packaged with a CLI utility `ensemblinator-tools` for use within jobs.

## Usage

From within a job, execute

    ensemblinator-tools <command> [args...]

In bash, this can simply be called as any other command. In other languages, it must be launched externally (for example, via `subprocess` in Python).

Produces exit code 2 on any error.

## Commands

### `job-state <subcommand> [args...]`

Allows for interacting with variables that persist between runs of the same job. Each job has its own set of variables. All variables are represented as strings.

#### Subcommands

**`get <key>`** - sends the value of variable `key` to stdout. If unset, exits with code 1 and no output.

**`set <key> <value>`** - sets the variable `key` to `value`. No output.

**`delete <key>`** - deletes the variable `key`, if it exists. No output.
