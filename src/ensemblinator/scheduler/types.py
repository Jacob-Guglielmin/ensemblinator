from dataclasses import dataclass
from enum import Enum


class TriggerEvent(Enum):
    SYSTEM_UP = "system: up"
    SYSTEM_DOWN = "system: down"
    NETWORK_UP = "network: up"
    NETWORK_DOWN = "network: down"


@dataclass(frozen=True)
class CronSchedule:
    expression: str


@dataclass(frozen=True)
class EventSchedule:
    event: TriggerEvent


Schedule = CronSchedule | EventSchedule


class JobRequirement(Enum):
    NETWORK = "network"


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
    schedules: list[Schedule]
    timeout: float
    requires: list[JobRequirement]
    notify: NotificationMeta | None
