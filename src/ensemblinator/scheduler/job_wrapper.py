from ensemblinator.scheduler.meta_parser import JobMeta
from ensemblinator.notifier import notifier

from pathlib import Path
import subprocess
import time
import os

def wrapped_job(executable: Path, meta: JobMeta, state_dir: Path):
    exit_code, output, duration = _execute_subprocess(meta.job_id, executable, state_dir, meta.timeout)

    print(f"[ensemblinator]: ran {meta.job_id}, exit code {exit_code}, took {duration:.1f}s")

    notifier.get().notify_job_complete(meta, exit_code, output, duration)

def _execute_subprocess(job_id: str, executable: Path, state_dir: Path, timeout: float) -> tuple[int, str, float]:
    env = os.environ.copy()
    env["JOB_ID"] = job_id
    env["STATE_DIR"] = str(state_dir)

    start = time.monotonic()
    try:
        result = subprocess.run(
            ["timeout", "--kill-after=5", f"{timeout}s", str(executable)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
            env=env
        )
        stdout = result.stdout.strip()
        if result.returncode in (124, 137):
            stdout += f"\n[ensemblinator]: timed out after {timeout}s, process killed"
        return result.returncode, stdout, time.monotonic() - start
    except Exception as e:
        return 127, f"[ensemblinator]: failed to launch process: {e}", time.monotonic() - start
