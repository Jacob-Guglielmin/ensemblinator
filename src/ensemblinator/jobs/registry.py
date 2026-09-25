import hashlib
import logging
import sys

from ensemblinator.jobs.meta_parser import MetaParseError, parse_job_header
from ensemblinator.jobs.models import Job

_logger = logging.getLogger(__name__)


_SKIPPED_DISCOVERY_DIRS = {"node_modules", "__pycache__", ".git"}


class JobRegistry:
    def __init__(self, jobs_directory):
        self._jobs_dir = jobs_directory
        self._jobs: list[Job] = []

    def discover(self) -> list[Job]:
        if len(self._jobs) != 0:
            _logger.error("Jobs already discovered")
            sys.exit(1)

        for path in sorted(self._jobs_dir.rglob("*")):
            if not path.is_file():
                continue
            if any(
                part in _SKIPPED_DISCOVERY_DIRS for part in path.relative_to(self._jobs_dir).parts
            ):
                continue

            try:
                meta = parse_job_header(path, self._jobs_dir)
            except MetaParseError as e:
                _logger.error(f"{e!s} ({path.relative_to(self._jobs_dir)})")
                continue

            if meta is None:
                continue

            job_hash = hashlib.sha256(path.read_bytes()).hexdigest()

            dup_job = next((job for job in self._jobs if job.meta.job_id == meta.job_id), None)
            if dup_job is not None:
                _logger.error(f"Duplicate job id '{meta.job_id}': {path}, {dup_job.executable}")
                sys.exit(1)

            self._jobs.append(Job(meta=meta, executable=path, expected_hash=job_hash))

        return self._jobs

    def jobs(self) -> list[Job]:
        return self._jobs
