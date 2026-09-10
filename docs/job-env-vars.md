# Job environment variables

Jobs are run with some preset environment variables

## Utilities

### `JOB_TRIGGER`

Stores the cause of the current job run, using the text after the relevant `@schedule` directive. For example, if the schedule that caused the current job run was `# @schedule cron: 0 3 * * *`, the value of `JOB_TRIGGER` would be `cron: 0 3 * * *`.

For manual job runs, this value is always `manual`.

## Internal

### `JOB_ID`

Stores the internal job id of the job that is running.

### `STATE_DIR`

Stores the absolute path to the state directory configured in [`ensemblinator.toml`](./conf-examples/ensemblinator.toml).
