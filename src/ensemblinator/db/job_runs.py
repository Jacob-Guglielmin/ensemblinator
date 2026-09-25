import time

from ensemblinator.db.connection import ConnectionProvider


class _JobRunsMethods(ConnectionProvider):
    def run_start(self, job_id: str, trigger: str) -> int:
        cur = self._connection().execute(
            "INSERT INTO job_runs (job_id, started_at, status, trigger) VALUES (?, ?, 'pending', ?)",
            (job_id, time.time(), trigger),
        )
        self._connection().commit()

        assert cur.lastrowid is not None
        return cur.lastrowid

    def run_skip(self, job_id: str, trigger: str, skip_reason: str) -> int:
        cur = self._connection().execute(
            "INSERT INTO job_runs (job_id, started_at, status, trigger, skip_reason) VALUES (?, ?, 'skipped', ?, ?)",
            (job_id, time.time(), trigger, skip_reason),
        )
        self._connection().commit()

        assert cur.lastrowid is not None
        return cur.lastrowid

    def run_finish(self, run_id: int, status: str, exit_code: int | None, log_content: str) -> None:
        self._connection().execute(
            "UPDATE job_runs SET finished_at=?, status=?, exit_code=? WHERE run_id=?",
            (time.time(), status, exit_code, run_id),
        )
        self._connection().execute(
            "INSERT INTO job_run_logs (run_id, content) VALUES (?, ?)",
            (run_id, log_content)
        )
        self._connection().commit()
