from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SuccessNotificationLevel(Enum):
    ALL = "all"
    NOISY = "noisy"
    NONE = "none"


class TriggerEvent(Enum):
    SYSTEM_UP = "system: up"
    SYSTEM_DOWN = "system: down"
    NETWORK_UP = "network: up"
    NETWORK_DOWN = "network: down"


class Schedule(ABC):
    @abstractmethod
    def __str__(self) -> str: ...


@dataclass(frozen=True)
class CronSchedule(Schedule):
    expression: str

    def __str__(self) -> str:
        return f"cron: {self.expression}"


@dataclass(frozen=True)
class EventSchedule(Schedule):
    event: TriggerEvent

    def __str__(self) -> str:
        return self.event.value


class JobRequirement(Enum):
    NETWORK = "network"


@dataclass(frozen=True)
class NotificationMeta:
    channels: list[str]
    success_notifications: SuccessNotificationLevel
    heartbeat_interval: float
    consecutive_failures: int


@dataclass(frozen=True)
class JobMeta:
    job_id: str
    schedules: list[Schedule]
    timeout: float
    requires: list[JobRequirement]
    notify: NotificationMeta | None


@dataclass(frozen=True)
class Job:
    meta: JobMeta
    executable: Path
    expected_hash: str
