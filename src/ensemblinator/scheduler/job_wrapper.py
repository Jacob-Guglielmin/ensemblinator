from ensemblinator.scheduler.meta_parser import JobMeta
from ensemblinator.common.notifier import notifier
from ensemblinator.common import common

from pathlib import Path
import subprocess
import time
import os

def wrapped_job(executable: Path, meta: JobMeta):
    exit_code, output, duration = _execute_subprocess(meta.job_id, executable, meta.timeout)

    print(exit_code, duration, meta)

    notifier.get().notify_job_complete(meta, exit_code, output, duration)

def _execute_subprocess(job_id: str, executable: Path, timeout: float) -> tuple[int, str, float]:
    env = os.environ.copy()
    env["JOB_ID"] = job_id
    env["PATH"] = f"{common.SRC_DIR / "cli" / "bin"}:{env.get("PATH", "")}"

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
