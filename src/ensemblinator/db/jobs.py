import json

from ensemblinator.db.connection import ConnectionProvider
from ensemblinator.jobs.models import Job


class _JobsWriteMethods(ConnectionProvider):
    def rebuild_jobs(self, jobs: list[Job]) -> None:
        self._connection().execute("DELETE FROM jobs")
        self._connection().executemany(
            "INSERT INTO jobs (job_id, file_hash, executable_path, schedules, timeout, requirements) VALUES (?, ?, ?, ?, ?, ?)",
            (
                (
                    job.meta.job_id,
                    job.expected_hash,
                    job.executable.as_posix(),
                    json.dumps([str(schedule) for schedule in job.meta.schedules]),
                    job.meta.timeout,
                    json.dumps([requirement.value for requirement in job.meta.requires]),
                )
                for job in jobs
            ),
        )
        self._connection().commit()
