# Meta directive reference

Jobs are configured via meta directives in their header comments.

## Syntax

Meta directives appear in comments at the top of the file. All directives must appear before any non-comment content, though may be interspersed with comments/shebang/etc. Parsing stops at the first line that is neither a comment nor entirely whitespace. For example:

    #!/usr/bin/env bash
    # This is a job.
    # @job my-job

    # This job runs every day at 03:00 UTC.
    # @schedule cron: 0 3 * * *

    <job code>


## Directives

### `@job [name]` (**required**)

Marks this file as a job. The name, if provided, is used for identification and will be prepended to any notifications sent on behalf of this job.

    # @job my-job

### `@schedule <type>: <value>` (**required**, multi)

Determines when the job runs. Supported types:

**`cron: <expression>`** - Standard cron syntax (UTC), runs on schedule.

    # @schedule cron: 0 3 * * *

**`system: <up|down>`** - Runs once, when ensemblinator starts/shuts down cleanly. Will not run on unclean shutdown (power loss, SIGKILL, etc.). Note that this schedule will change the default timeout to 45 seconds, and cause an error if a timeout greater than that is specified.

    # @schedule system: up

**`network: <up|down>`** - Runs once whenever network connectivity enters the given state. Connectivity is tested every ten seconds. Three consecutive results are required to toggle the state, to prevent flaky connections from causing false events.

    # @schedule network: up

### `@timeout: <seconds>` (optional, default: 3600)

Maximum runtime in seconds. Jobs which reach their timeout are sent SIGTERM, then SIGKILL after 5 seconds if they continue running. Note that jobs running on a `system` `@schedule` will have a default of 45 seconds, and will not accept values larger than that passed manually.

    # @timeout 60

### `@requires: <requirement>` (optional)

Sets requirements that must be met before running the job. If a requirement is not met, the job will be skipped with an error.

**Available requirements:** `network`

### `@notify.channel <name>` (optional, but **required** if any `@notify.*` directives are present, multi)

Discord channel to send notifications to. May appear multiple times. Channel must exist in [`ensemblinator.toml`](./conf-examples/ensemblinator.toml).

    # @notify.channel my-job-status
    # @notify.channel all-logs

### `@notify.quiet-success` (flag)

Suppress notifications for successful runs (exit code 0) which produce no output. Failures and noisy successes still notify as usual.

    # @notify.quiet-success

### `@notify.heartbeat-interval <seconds>` (optional, default: 86400)

When used with `@notify.quiet-success`, pushes a success notification through anyway if at least this much time has passed since the previous notification. A value of 0 suppresses heartbeats.

    # @notify.heartbeat-interval 3600

### `@notify.consecutive-failures <count>` (optional, default: 1)

Prevents error pings on job failure (exit code != 0) until this many failures have occurred in a row. Logs will still be sent as normal - only applies to messages destined for the errors channel.

    # @notify.consecutive-failures 3
