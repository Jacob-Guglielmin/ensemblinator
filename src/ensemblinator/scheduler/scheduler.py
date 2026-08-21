from ensemblinator.common import common
from ensemblinator.common.notifier import notifier
from ensemblinator.scheduler.meta_parser import parse_job_header, SystemEvent, MetaParseError, CronSchedule, SystemSchedule
from ensemblinator.scheduler.job_wrapper import wrapped_job

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pathlib import Path
from datetime import timezone
import atexit

class Scheduler:
    def __init__(self, jobs_dir: Path):
        self._jobs_dir = jobs_dir

        job_defaults = {
            "misfire_grace_time": 5*60
        }
        self._scheduler = BackgroundScheduler(job_defaults=job_defaults, timezone=timezone.utc)

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
                        kwargs={"executable": path, "meta": meta},
                        id=meta.job_id,
                        name=meta.job_id
                    )
                case SystemSchedule():
                    self._system_scheduled[meta.schedule.event].append(
                        {"executable": path, "meta": meta}
                    )
                case _:
                    raise NotImplementedError(f"No scheduler handling for schedule type {type(meta.schedule).__name__}")

    def _discover_jobs(self):
        for path in sorted(self._jobs_dir.rglob("*")):
            if not path.is_file():
                continue
            if any(part in common.SKIPPED_DISCOVERY_DIRS for part in path.relative_to(self._jobs_dir).parts):
                continue

            try:
                meta = parse_job_header(path, self._jobs_dir)
            except MetaParseError as e:
                notifier.get().notify([], f"[ensemblinator] {str(e)} ({path.relative_to(self._jobs_dir)})", error=True)
                continue

            if meta is None:
                continue

            yield path, meta

    def _execute_system_schedule(self, schedule: SystemEvent):
        jobs = self._system_scheduled[schedule]

        for job in jobs:
            wrapped_job(job["executable"], job["meta"])

    def _shutdown(self):
        print("shutting down scheduler")
        self._scheduler.shutdown(wait=False)
        if len(self._system_scheduled[SystemEvent.DOWN]) > 0:
            print("executing system down jobs")
            self._execute_system_schedule(SystemEvent.DOWN)
