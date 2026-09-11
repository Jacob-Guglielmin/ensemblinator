import hashlib
import logging
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from ensemblinator.connectivity.connectivity import has_connectivity
from ensemblinator.notifier import notifier
from ensemblinator.scheduler.types import Job, JobRequirement

_logger = logging.getLogger(__name__)


def wrapped_job(job: Job, state_dir: Path, trigger: str):
    try:
        job_content_bytes = job.executable.read_bytes()
    except FileNotFoundError:
        _logger.info(f"skipped {job.meta.job_id}: job file no longer exists")
        notifier.get().notify_job_skipped(job.meta, "job file no longer exists")
        return
    except PermissionError:
        _logger.info(f"skipped {job.meta.job_id}: insufficient permissions to read job file")
        notifier.get().notify_job_skipped(job.meta, "insufficient permissions to read job file")
        return
    except IsADirectoryError:
        _logger.info(f"skipped {job.meta.job_id}: directory found at previous location of job file")
        notifier.get().notify_job_skipped(
            job.meta, "directory found at previous location of job file"
        )
        return
    except OSError as e:
        _logger.info(f"skipped {job.meta.job_id}: unknown error reading job file: {e}")
        notifier.get().notify_job_skipped(job.meta, f"unknown error reading job file: {e}")
        return

    if (
        job.expected_hash is not None
        and hashlib.sha256(job_content_bytes).hexdigest() != job.expected_hash
    ):
        _logger.info(f"skipped {job.meta.job_id}: job file has changed on disk")
        notifier.get().notify_job_skipped(job.meta, "job file has changed on disk")
        return

    unmet_reqs = _validate_requirements(job.meta.requires)

    if not unmet_reqs:
        exit_code, output, duration = _execute_subprocess(
            job.meta.job_id, job.executable, state_dir, job.meta.timeout, trigger
        )

        _logger.info(
            f"ran {job.meta.job_id}, trigger '{trigger}', exit code {exit_code}, took {duration:.1f}s"
        )

        notifier.get().notify_job_complete(job.meta, exit_code, output, duration)
    else:
        _logger.info(f"skipped {job.meta.job_id}: {', '.join(unmet_reqs)}")
        notifier.get().notify_job_skipped(job.meta, ", ".join(unmet_reqs))


class Check(NamedTuple):
    is_met: Callable[[], bool]
    description: str


_CHECKS: dict[JobRequirement, Check] = {
    JobRequirement.NETWORK: Check(has_connectivity, "network access required")
}


def _validate_requirements(requirements: list[JobRequirement]) -> list[str]:
    return [_CHECKS[r].description for r in requirements if not _CHECKS[r].is_met()]


def _execute_subprocess(
    job_id: str, executable: Path, state_dir: Path, timeout: float, trigger: str
) -> tuple[int, str, float]:
    env = os.environ.copy()
    env["JOB_ID"] = job_id
    env["STATE_DIR"] = str(state_dir)
    env["JOB_TRIGGER"] = trigger
    tools_dir = Path.home() / ".local" / "bin"
    env["PATH"] = f"{tools_dir}:{env.get('PATH', '')}"

    start = time.monotonic()
    try:
        result = subprocess.run(
            ["timeout", "--kill-after=5", f"{timeout}s", str(executable)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
            env=env,
            check=False,
        )
        stdout = result.stdout.strip()
        if result.returncode in (124, 137):
            stdout += f"\n[ensemblinator]: timed out after {timeout}s, process killed"
        return result.returncode, stdout, time.monotonic() - start
    except OSError as e:
        return 127, f"[ensemblinator]: failed to launch process: {e}", time.monotonic() - start
