from ensemblinator.common.notifier import notifier

import re
from pathlib import Path
from typing import Callable, Any
from enum import Enum
from dataclasses import dataclass

class MetaParseError(Exception):
    pass

class SystemEvent(Enum):
    UP = "up"
    DOWN = "down"

@dataclass(frozen=True)
class CronSchedule:
    expression: str

@dataclass(frozen=True)
class SystemSchedule:
    event: SystemEvent

Schedule = CronSchedule | SystemSchedule

@dataclass(frozen=True)
class NotificationMeta:
    channels: list[str]
    quiet_success: bool
    heartbeat_interval: float
    consecutive_failures: int

@dataclass(frozen=True)
class JobMeta:
    job_id: str
    name: str | None
    schedule: Schedule
    timeout: float
    notify: NotificationMeta | None

@dataclass(frozen=True)
class DirectiveSpec:
    name: str # the directive's name, without the @
    required: bool = False
    multi: bool = False # allows repeated @directive lines, resulting in a list of values
    flag: bool = False # expect no value
    parse: Callable[[str, str], Any] | None = None # called on the value if present, converts str -> appropriate data
    default: Any = None # value to use if no @directive line present and directive not required

    def __post_init__(self):
        if self.flag and self.required:
            raise ValueError(f"DirectiveSpec {self.name!r}: it is nonsensical for a flag to be required")
        if self.flag and self.multi:
            raise ValueError(f"DirectiveSpec {self.name!r}: it is nonsensical to allow multiple copies of a flag")
        if self.flag and (self.parse is not None):
            raise ValueError(f"DirectiveSpec {self.name!r}: it is nonsensical to have parsing logic for a flag")
        if self.flag and (self.default is not None):
            raise ValueError(f"DirectiveSpec {self.name!r}: it is nonsensical to have a custom default for a flag")
        if self.multi and (self.default is not None):
            raise ValueError(f"DirectiveSpec {self.name!r}: it is nonsensical to have a custom default for a multi directive")

COMMENT_PREFIXES = ["#", "//"]

def _build_meta_regex():
    options = "|".join(re.escape(prefix) for prefix in COMMENT_PREFIXES)
    return re.compile(rf"^\s*(?:{options})\s*@(\S+)\s*(.*)")
META_LINE = _build_meta_regex()

def _parse_positive_float(spec_name: str, v: str) -> float:
    try:
        v = float(v)
        if v < 0:
            raise MetaParseError(f"job's @{spec_name} directive must be positive")
    except ValueError:
        raise MetaParseError(f"job's @{spec_name} directive must be a positive number")
    
def _parse_positive_int(spec_name: str, v: str) -> int:
    try:
        v = int(v)
        if v < 0:
            raise MetaParseError(f"job's @{spec_name} directive must be positive")
    except ValueError:
        raise MetaParseError(f"job's @{spec_name} directive must be a positive integer")

def _parse_channel(spec_name: str, v: str) -> str:
    if not notifier.get().channel_exists(v):
        raise MetaParseError(f"job contains @{spec_name} directive with reference to unknown channel '{v}'")
    return v

def _parse_schedule(spec_name: str, v: str) -> Schedule:
    schedule_type, _, rest = v.partition(": ")
    rest = rest.strip()

    if schedule_type == "cron":
        return CronSchedule(rest)
    
    if schedule_type == "system":
        try:
            return SystemSchedule(SystemEvent(rest))
        except ValueError:
            raise MetaParseError(f"job's @{spec_name} directive could not be parsed: '{rest}' is not a system schedule")

    raise MetaParseError(f"job's @{spec_name} directive type '{schedule_type}' does not exist")

DIRECTIVES = [
    DirectiveSpec(name="job", required=True),
    DirectiveSpec(name="schedule", required=True, parse=_parse_schedule),
    DirectiveSpec(name="timeout", parse=_parse_positive_float, default=3600.0),
    DirectiveSpec(name="notify.channel", multi=True, parse=_parse_channel),
    DirectiveSpec(name="notify.quiet-success", flag=True),
    DirectiveSpec(name="notify.heartbeat-interval", parse=_parse_positive_float, default=86400.0),
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

    return _interpret_meta(path.relative_to(jobs_dir).as_posix(), meta)

def _interpret_directives(raw_meta: dict) -> dict[str, Any]:
    by_name = {d.name: d for d in DIRECTIVES}
    passed = set(raw_meta.keys())

    unknown = passed - by_name.keys()
    if unknown:
        raise MetaParseError(f"job contains unknown directive(s): {", ".join([f"@{d}" for d in unknown])}")

    missing = {d.name for d in DIRECTIVES if d.required} - passed
    if missing:
        raise MetaParseError(f"job is missing required directive(s): {", ".join([f"@{d}" for d in missing])}")

    values={}
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

        if isinstance(raw, list) and not spec.multi:
            raise MetaParseError(f"job contains multiple @{spec.name} directives, only one permitted")

        if spec.flag:
            if raw != "":
                raise MetaParseError(f"job's @{spec.name} flag directive was passed data")
            values[spec.name] = True
        elif spec.multi:
            values[spec.name] = [spec.parse(spec.name, v) if spec.parse else v for v in raw]
        else:
            values[spec.name] = spec.parse(spec.name, raw) if spec.parse else raw

    return values

def _interpret_meta(job_id: str, raw_meta: dict) -> JobMeta:
    values = _interpret_directives(raw_meta)

    notify_directives_passed = any(k.startswith("notify.") for k in raw_meta)
    if notify_directives_passed:
        if not values["notify.channel"]:
            raise MetaParseError(f"job contains @notify.* directives but no @notify.channel directives")
        notify = NotificationMeta(
            channels=values["notify.channel"],
            quiet_success=values["notify.quiet-success"],
            heartbeat_interval=values["notify.heartbeat-interval"],
            consecutive_failures=values["notify.consecutive-failures"]
        )
    else:
        notify = None

    meta = JobMeta(
        job_id=job_id,
        name=values["job"] if values["job"] else None,
        schedule=values["schedule"],
        timeout=values["timeout"],
        notify=notify
    )

    return meta
