import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apscheduler.triggers.cron import CronTrigger

from ensemblinator.notifier import notifier
from ensemblinator.scheduler.types import (
    CronSchedule,
    EventSchedule,
    JobMeta,
    JobRequirement,
    NotificationMeta,
    Schedule,
    TriggerEvent,
)


class MetaParseError(Exception):
    pass


@dataclass(frozen=True)
class DirectiveSpec:
    name: str  # the directive's name, without the @
    required: bool = False
    multi: bool = False  # allows repeated @directive lines, resulting in a list of values
    flag: bool = False  # expect no value
    parse: Callable[[str, str], Any] | None = (
        None  # called on the value if present, converts str -> appropriate data
    )
    default: Any = None  # value to use if no @directive line present and directive not required

    def __post_init__(self):
        if self.flag and self.required:
            raise ValueError(
                f"DirectiveSpec {self.name!r}: it is nonsensical for a flag to be required"
            )
        if self.flag and self.multi:
            raise ValueError(
                f"DirectiveSpec {self.name!r}: it is nonsensical to allow multiple copies of a flag"
            )
        if self.flag and (self.parse is not None):
            raise ValueError(
                f"DirectiveSpec {self.name!r}: it is nonsensical to have parsing logic for a flag"
            )
        if self.flag and (self.default is not None):
            raise ValueError(
                f"DirectiveSpec {self.name!r}: it is nonsensical to have a custom default for a flag"
            )
        if self.multi and (self.default is not None):
            raise ValueError(
                f"DirectiveSpec {self.name!r}: it is nonsensical to have a custom default for a multi directive"
            )


COMMENT_PREFIXES = ["#", "//"]


def _build_meta_regex():
    options = "|".join(re.escape(prefix) for prefix in COMMENT_PREFIXES)
    return re.compile(rf"^\s*(?:{options})\s*@(\S+)\s*(.*)")


META_LINE = _build_meta_regex()


def _parse_positive_float(spec_name: str, v: str) -> float:
    try:
        float_v = float(v)
        if float_v <= 0:
            raise MetaParseError(f"job's @{spec_name} directive must be positive")
    except ValueError:
        raise MetaParseError(f"job's @{spec_name} directive must be a positive number")
    return float_v


def _parse_nonneg_float(spec_name: str, v: str) -> float:
    try:
        float_v = float(v)
        if float_v < 0:
            raise MetaParseError(f"job's @{spec_name} directive must be non-negative")
    except ValueError:
        raise MetaParseError(f"job's @{spec_name} directive must be a non-negative number")
    return float_v


def _parse_positive_int(spec_name: str, v: str) -> int:
    try:
        int_v = int(v)
        if int_v <= 0:
            raise MetaParseError(f"job's @{spec_name} directive must be positive")
    except ValueError:
        raise MetaParseError(f"job's @{spec_name} directive must be a positive integer")
    return int_v


def _parse_nonneg_int(spec_name: str, v: str) -> int:
    try:
        int_v = int(v)
        if int_v < 0:
            raise MetaParseError(f"job's @{spec_name} directive must be non-negative")
    except ValueError:
        raise MetaParseError(f"job's @{spec_name} directive must be a non-negative integer")
    return int_v


def _parse_requires(spec_name: str, v: str) -> JobRequirement:
    try:
        return JobRequirement(v)
    except ValueError:
        raise MetaParseError(f"job's @{spec_name} directive references unknown requirement '{v}'")


def _parse_channel(spec_name: str, v: str) -> str:
    if not notifier.get().channel_exists(v):
        raise MetaParseError(f"job's @{spec_name} directive references unknown channel '{v}'")
    return v


def _parse_schedule(spec_name: str, v: str) -> Schedule:
    schedule_type, _, rest = v.partition(": ")
    rest = rest.strip()

    if schedule_type == "cron":
        try:
            CronTrigger.from_crontab(rest)
            return CronSchedule(rest)
        except ValueError as e:
            raise MetaParseError(
                f"job's @{spec_name} directive contains an invalid cron expression '{e}'"
            )

    if schedule_type in ["system", "network"]:
        try:
            return EventSchedule(TriggerEvent(f"{schedule_type}: {rest}"))
        except ValueError:
            raise MetaParseError(
                f"job's @{spec_name} directive contains an invalid {schedule_type} schedule '{rest}'"
            )

    raise MetaParseError(
        f"job's @{spec_name} directive references an unknown schedule type '{schedule_type}'"
    )


DIRECTIVES = [
    DirectiveSpec(name="job", required=True),
    DirectiveSpec(name="schedule", required=True, multi=True, parse=_parse_schedule),
    DirectiveSpec(name="timeout", parse=_parse_positive_float, default=3600.0),
    DirectiveSpec(name="requires", parse=_parse_requires, multi=True),
    DirectiveSpec(name="notify.channel", multi=True, parse=_parse_channel),
    DirectiveSpec(name="notify.quiet-success", flag=True),
    DirectiveSpec(name="notify.heartbeat-interval", parse=_parse_nonneg_float, default=86400.0),
    DirectiveSpec(name="notify.consecutive-failures", parse=_parse_positive_int, default=1),
]


def parse_job_header(path: Path, jobs_dir: Path) -> JobMeta | None:
    meta = {}

    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.strip()

            if not stripped:
                # Blank line
                continue

            m = META_LINE.match(stripped)
            if m:
                key = m.group(1)
                value = m.group(2).strip()
                current = meta.get(key, None)
                if current is not None:
                    if isinstance(current, list):
                        meta[key] = current + [value]
                    else:
                        meta[key] = [current, value]
                else:
                    meta[key] = value
                continue

            if any(stripped.startswith(prefix) for prefix in COMMENT_PREFIXES):
                # Irrelevant comment/shebang
                continue

            # Real file contents: exit here
            break

    if meta.get("job", None) is None:
        return None

    return _interpret_meta(path.resolve().relative_to(jobs_dir).as_posix(), meta)


def _interpret_directives(raw_meta: dict[str, str | list[str]]) -> dict[str, Any]:
    by_name = {d.name: d for d in DIRECTIVES}
    passed = set(raw_meta.keys())

    unknown = passed - by_name.keys()
    if unknown:
        raise MetaParseError(
            f"job contains unknown directive(s): {', '.join([f'@{d}' for d in unknown])}"
        )

    missing = {d.name for d in DIRECTIVES if d.required} - passed
    if missing:
        raise MetaParseError(
            f"job is missing required directive(s): {', '.join([f'@{d}' for d in missing])}"
        )

    values = {}
    for spec in DIRECTIVES:
        raw = raw_meta.get(spec.name)

        if raw is None:
            if spec.flag:
                values[spec.name] = False
            elif spec.multi:
                values[spec.name] = []
            else:
                values[spec.name] = spec.default
            continue

        if spec.flag:
            if raw != "":
                raise MetaParseError(f"job's @{spec.name} flag directive was passed data")
            values[spec.name] = True
            continue

        if isinstance(raw, list):
            if spec.multi:
                values[spec.name] = [spec.parse(spec.name, v) if spec.parse else v for v in raw]
            else:
                raise MetaParseError(
                    f"job contains multiple @{spec.name} directives, only one permitted"
                )
        else:
            if spec.multi:
                values[spec.name] = [spec.parse(spec.name, raw) if spec.parse else raw]
            else:
                values[spec.name] = spec.parse(spec.name, raw) if spec.parse else raw

    return values


def _interpret_meta(job_id: str, raw_meta: dict) -> JobMeta:
    values = _interpret_directives(raw_meta)

    notify_directives_passed = any(k.startswith("notify.") for k in raw_meta)
    if notify_directives_passed:
        if not values["notify.channel"]:
            raise MetaParseError(
                "job contains @notify.* directives but no @notify.channel directives"
            )
        notify = NotificationMeta(
            channels=values["notify.channel"],
            quiet_success=values["notify.quiet-success"],
            heartbeat_interval=values["notify.heartbeat-interval"],
            consecutive_failures=values["notify.consecutive-failures"],
        )
    else:
        notify = None

    if any(
        isinstance(schedule, EventSchedule)
        and schedule.event in [TriggerEvent.SYSTEM_UP, TriggerEvent.SYSTEM_DOWN]
        for schedule in values["schedule"]
    ):
        if float(raw_meta.get("timeout", 0)) > 45:
            raise MetaParseError(
                "job is using a system @schedule, but includes a timeout of >45 seconds"
            )
        else:
            values["timeout"] = min(45, values["timeout"])

    seen_schedules = []
    for schedule in values["schedule"]:
        if schedule in seen_schedules:
            raise MetaParseError("job contains duplicate @schedule directives")
        seen_schedules.append(schedule)

    meta = JobMeta(
        job_id=job_id,
        name=values["job"] if values["job"] else None,
        schedules=values["schedule"],
        timeout=values["timeout"],
        requires=values["requires"],
        notify=notify,
    )

    return meta
