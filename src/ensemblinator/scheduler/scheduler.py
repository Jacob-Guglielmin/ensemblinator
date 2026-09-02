import atexit
import logging
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import UTC
from pathlib import Path
from typing import NamedTuple

from apscheduler.events import EVENT_JOB_ERROR
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ensemblinator import error_handlers
from ensemblinator.connectivity.connectivity_monitor import ConnectivityMonitor
from ensemblinator.notifier import notifier
from ensemblinator.scheduler.job_wrapper import wrapped_job
from ensemblinator.scheduler.meta_parser import (
    CronSchedule,
    EventSchedule,
    JobMeta,
    MetaParseError,
    TriggerEvent,
    parse_job_header,
)

_logger = logging.getLogger(__name__)

_SKIPPED_DISCOVERY_DIRS = {"node_modules", "__pycache__", ".git"}


class Job(NamedTuple):
    executable: Path
    meta: JobMeta


class Scheduler:
    def __init__(self, jobs_dir: Path, state_dir: Path):
        self._jobs_dir = jobs_dir
        self._state_dir = state_dir

        self._network_up: bool | None = None
        self._network_consecutive: int = 0

        job_defaults = {"misfire_grace_time": 5 * 60}
        self._scheduler = BackgroundScheduler(job_defaults=job_defaults, timezone=UTC)
        self._scheduler.add_listener(error_handlers.handle_job_error, EVENT_JOB_ERROR)

        self._connectivity_monitor = ConnectivityMonitor(
            10,
            3,
            on_transition=self._network_transition,
            on_up_periodic=notifier.get().flush_pending,
        )

        self._event_scheduled: defaultdict[TriggerEvent, list[Job]] = defaultdict(list)

    def start(self):
        self._execute_event_schedule(TriggerEvent.SYSTEM_UP)

        self._scheduler.start()
        self._connectivity_monitor.start()
        atexit.register(self._shutdown)

    def register_jobs(self):
        for path, meta in self._discover_jobs():
            for schedule in meta.schedules:
                match schedule:
                    case CronSchedule():
                        self._scheduler.add_job(
                            func=wrapped_job,
                            trigger=CronTrigger.from_crontab(schedule.expression),
                            kwargs={
                                "executable": path,
                                "meta": meta,
                                "state_dir": self._state_dir,
                                "trigger": f"cron: {schedule.expression}",
                            },
                            id=meta.job_id,
                            name=meta.job_id,
                        )
                    case EventSchedule():
                        self._event_scheduled[schedule.event].append(Job(path, meta))
                    case _:
                        raise NotImplementedError(
                            f"No scheduler handling for schedule type {type(schedule).__name__}"
                        )

    def run_immediate(self, executable: Path):
        executable = executable.resolve()

        try:
            meta = parse_job_header(executable, self._jobs_dir)
        except MetaParseError as e:
            _logger.error(str(e))
            sys.exit(1)

        if meta is None:
            _logger.error("no @job directive detected")
            sys.exit(1)

        wrapped_job(executable, meta, self._state_dir, "manual")

    def _discover_jobs(self):
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

            yield path, meta

    def _execute_event_schedule(self, event: TriggerEvent):
        jobs = self._event_scheduled[event]
        if not jobs:
            return

        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = {
                pool.submit(
                    wrapped_job, job.executable, job.meta, self._state_dir, event.value
                ): job
                for job in jobs
            }
            done, not_done = wait(
                futures.keys(), timeout=max(job.meta.timeout for job in jobs) + 10
            )

            if len(not_done) > 0:
                _logger.error(
                    f"system {event.name} job batch did not complete within the required timeout (likely an internal issue)"
                )

            for future in done:
                exc = future.exception()
                if exc is not None:
                    job = futures[future]
                    error_handlers.notify_crash(exc, f"system @schedule job {job.meta.job_id}")

    def _network_transition(self, network_up: bool):
        _logger.warning(f"network transition: {'up' if network_up else 'down'}")
        event = TriggerEvent.NETWORK_UP if network_up else TriggerEvent.NETWORK_DOWN
        self._execute_event_schedule(event)

    def _shutdown(self):
        _logger.info("shutting down scheduler...")
        self._connectivity_monitor.stop()
        self._scheduler.shutdown(wait=False)
        if len(self._event_scheduled[TriggerEvent.SYSTEM_DOWN]) > 0:
            _logger.info("executing system down jobs...")
            self._execute_event_schedule(TriggerEvent.SYSTEM_DOWN)
        _logger.info("scheduler shutdown complete")
