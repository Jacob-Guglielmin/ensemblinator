from ensemblinator.db.connection import ConnectionProvider


class _JobStateMethods(ConnectionProvider):
    def get_job_state(self, job_id: str, key: str) -> str | None:
        row = (
            self._connection()
            .execute("SELECT value FROM job_state WHERE job_id=? AND key=?", (job_id, key))
            .fetchone()
        )
        return row[0] if row else None

    def set_job_state(self, job_id: str, key: str, value: str) -> None:
        self._connection().execute(
            "INSERT OR REPLACE INTO job_state VALUES (?, ?, ?)", (job_id, key, value)
        )
        self._connection().commit()

    def delete_job_state(self, job_id: str, key: str) -> None:
        self._connection().execute("DELETE FROM job_state WHERE job_id=? AND key=?", (job_id, key))
        self._connection().commit()
