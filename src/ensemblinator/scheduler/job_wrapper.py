import logging
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from ensemblinator.connectivity.connectivity import has_connectivity
from ensemblinator.notifier import notifier
from ensemblinator.scheduler.meta_parser import JobMeta, JobRequirement

_logger = logging.getLogger(__name__)


def wrapped_job(executable: Path, meta: JobMeta, state_dir: Path, trigger: str):
    unmet_reqs = _validate_requirements(meta.requires)

    if not unmet_reqs:
        exit_code, output, duration = _execute_subprocess(
            meta.job_id, executable, state_dir, meta.timeout, trigger
        )

        _logger.info(f"ran {meta.job_id}, exit code {exit_code}, took {duration:.1f}s")

        notifier.get().notify_job_complete(meta, exit_code, output, duration)
    else:
        notifier.get().notify_job_skipped(meta, ", ".join(unmet_reqs))


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
