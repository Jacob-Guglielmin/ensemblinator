import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import UTC
from pathlib import Path

from apscheduler.events import EVENT_JOB_ERROR
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ensemblinator import error_handlers
from ensemblinator.connectivity.connectivity_monitor import ConnectivityMonitor
from ensemblinator.db.clients import Database
from ensemblinator.jobs.models import CronSchedule, EventSchedule, Job, TriggerEvent
from ensemblinator.notifier import notifier
from ensemblinator.scheduler.job_wrapper import wrapped_job

_logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, jobs: list[Job], database: Database, state_dir: Path):
        self._database = database
        self._state_dir = state_dir

        self._running: bool = False

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

        self._register_jobs(jobs)

    def start(self):
        self._execute_event_schedule(TriggerEvent.SYSTEM_UP)

        self._scheduler.start()
        self._connectivity_monitor.start()

        self._running = True

    def _register_jobs(self, jobs: list[Job]):
        job_ids_registered: list[str] = []
        for job in jobs:
            for schedule in job.meta.schedules:
                match schedule:
                    case CronSchedule():
                        self._scheduler.add_job(
                            func=wrapped_job,
                            trigger=CronTrigger.from_crontab(schedule.expression),
                            kwargs={
                                "job": job,
                                "database": self._database,
                                "state_dir": self._state_dir,
                                "trigger": str(schedule),
                            },
                            id=job.meta.job_id,
                            name=job.meta.job_id,
                        )
                    case EventSchedule():
                        self._event_scheduled[schedule.event].append(job)
                    case _:
                        raise NotImplementedError(
                            f"No scheduler handling for schedule type {type(schedule).__name__}"
                        )
            job_ids_registered.append(job.meta.job_id)
        _logger.info(
            f"registered {len(job_ids_registered)} job{'s' if len(job_ids_registered) != 1 else ''}:\n{'\n'.join(job_ids_registered)}"
        )

    def _execute_event_schedule(self, event: TriggerEvent, timeout_override: float | None = None):
        jobs = self._event_scheduled[event]
        if not jobs:
            return

        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = {
                pool.submit(wrapped_job, job, self._database, self._state_dir, event.value): job
                for job in jobs
            }

            if timeout_override is not None:
                timeout = timeout_override
            else:
                timeout = max(job.meta.timeout for job in jobs) + 5

            done, not_done = wait(
                futures.keys(), timeout
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

    def shutdown(self, timeout: float):
        if not self._running:
            return

        _logger.info("shutting down scheduler...")
        self._connectivity_monitor.stop()
        self._scheduler.shutdown(wait=False)
        if len(self._event_scheduled[TriggerEvent.SYSTEM_DOWN]) > 0:
            _logger.info("executing system down jobs...")
            self._execute_event_schedule(TriggerEvent.SYSTEM_DOWN, timeout_override=timeout)
        _logger.info("scheduler shutdown complete")
        self._running = False
