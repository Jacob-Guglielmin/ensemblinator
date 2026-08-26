from ensemblinator.notifier import notifier
from ensemblinator.scheduler.meta_parser import parse_job_header, SystemEvent, MetaParseError, CronSchedule, SystemSchedule
from ensemblinator.scheduler.job_wrapper import wrapped_job
from ensemblinator import error_handlers

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path
from datetime import timezone
import atexit
import sys
import logging
_logger = logging.getLogger(__name__)

_SKIPPED_DISCOVERY_DIRS = {"node_modules", "__pycache__", ".git"}

class Scheduler:
    def __init__(self, jobs_dir: Path, state_dir: Path):
        self._jobs_dir = jobs_dir
        self._state_dir = state_dir

        job_defaults = {
            "misfire_grace_time": 5*60
        }
        self._scheduler = BackgroundScheduler(job_defaults=job_defaults, timezone=timezone.utc)
        self._scheduler.add_listener(error_handlers.handle_job_error, EVENT_JOB_ERROR)

        self._system_scheduled = {
            SystemEvent.UP: [],
            SystemEvent.DOWN: []
        }

    def start(self):
        self._execute_system_schedule(SystemEvent.UP)
        
        self._scheduler.start()
        atexit.register(self._shutdown)

    def register_jobs(self):
        for path, meta in self._discover_jobs():
            match meta.schedule:
                case CronSchedule():
                    self._scheduler.add_job(
                        func=wrapped_job,
                        trigger=CronTrigger.from_crontab(meta.schedule.expression),
                        kwargs={"executable": path, "meta": meta, "state_dir": self._state_dir},
                        id=meta.job_id,
                        name=meta.job_id
                    )
                case SystemSchedule():
                    self._system_scheduled[meta.schedule.event].append(
                        {"executable": path, "meta": meta}
                    )
                case _:
                    raise NotImplementedError(f"No scheduler handling for schedule type {type(meta.schedule).__name__}")

    def run_immediate(self, executable: Path):
        executable = executable.resolve()

        try:
            meta = parse_job_header(executable, self._jobs_dir)
        except MetaParseError as e:
            _logger.error(f"[ensemblinator]: {str(e)}")
            sys.exit(1)

        if meta is None:
            _logger.error(f"[ensemblinator]: no @job directive detected")
            sys.exit(1)

        try:
            wrapped_job(executable, meta, self._state_dir)
        except Exception as e:
            error_handlers.notify_crash(e, f"manual job run {meta.job_id}")
            sys.exit(1)

    def _discover_jobs(self):
        for path in sorted(self._jobs_dir.rglob("*")):
            if not path.is_file():
                continue
            if any(part in _SKIPPED_DISCOVERY_DIRS for part in path.relative_to(self._jobs_dir).parts):
                continue

            try:
                meta = parse_job_header(path, self._jobs_dir)
            except MetaParseError as e:
                notifier.get().notify([], f"[ensemblinator]: {str(e)} ({path.relative_to(self._jobs_dir)})", error=True)
                continue

            if meta is None:
                continue

            yield path, meta

    def _execute_system_schedule(self, event: SystemEvent):
        jobs = self._system_scheduled[event]
        if not jobs:
            return

        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = {
                pool.submit(wrapped_job, job["executable"], job["meta"], self._state_dir): job
                for job in jobs
            }
            done, not_done = wait(futures.keys(), timeout=55)

            if len(not_done) > 0:
                notifier.get().notify([], f"[ensemblinator]: system {event.name} job batch did not complete within the required timeout (likely an internal issue)", True)

            for future in done:
                exc = future.exception()
                if exc is not None:
                    job = futures[future]
                    error_handlers.notify_crash(exc, f"system @schedule job {job["meta"].job_id}")

    def _shutdown(self):
        _logger.info("shutting down scheduler...")
        self._scheduler.shutdown(wait=False)
        if len(self._system_scheduled[SystemEvent.DOWN]) > 0:
            _logger.info("executing system down jobs...")
            self._execute_system_schedule(SystemEvent.DOWN)
        _logger.info("scheduler shutdown complete")
