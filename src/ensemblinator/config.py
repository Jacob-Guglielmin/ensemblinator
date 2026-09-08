import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PathsConfig:
    jobs_dir: Path
    state_dir: Path


@dataclass(frozen=True)
class NotifyConfig:
    guild_id: str
    webhooks: dict[str, str]


@dataclass(frozen=True)
class Config:
    paths: PathsConfig
    notify: NotifyConfig


def _require(data: dict, key: str, path_in_config_file: str) -> object:
    if key not in data:
        raise TypeError(f"missing required configuration value: {path_in_config_file}")
    return data[key]


def _resolve_config_path(value: str, config_dir: Path, path_in_config_file: str) -> Path:
    try:
        p = Path(value)
        if not p.is_absolute():
            p = config_dir / p
        return p.resolve()
    except (OSError, RuntimeError) as e:
        raise TypeError(
            f"expected a filesystem path in configuration value: {path_in_config_file}"
        ) from e


def load_config(config_path: Path):
    _logger.info("loading configuration...")

    config_path = config_path.resolve()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    paths = _require(data, "paths", "[paths]")
    if not isinstance(paths, dict):
        raise TypeError("[paths] must be a table")

    notify = _require(data, "notify", "[notify]")
    if not isinstance(notify, dict):
        raise TypeError("[notify] must be a table")

    webhooks = _require(notify, "webhooks", "[notify.webhooks]")
    if not isinstance(webhooks, dict):
        raise TypeError("[notify.webhooks] must be a table")

    jobs_dir = _require(paths, "jobs_dir", "[paths].jobs_dir")
    state_dir = _require(paths, "state_dir", "[paths].state_dir")
    guild_id = _require(notify, "guild_id", "[notify].guild_id")
    _require(webhooks, "errors", "[notify.webhooks].errors")

    if not isinstance(jobs_dir, str):
        raise TypeError("[paths].jobs_dir must be a string")
    if not isinstance(state_dir, str):
        raise TypeError("[paths].state_dir must be a string")
    if not isinstance(guild_id, str):
        raise TypeError("[notify].guild_id must be a string")
    if not all(isinstance(v, str) for v in webhooks.values()):
        raise TypeError("[notify.webhooks] values must all be strings")

    return Config(
        paths=PathsConfig(
            jobs_dir=_resolve_config_path(jobs_dir, config_path.parent, "[paths].jobs_dir"),
            state_dir=_resolve_config_path(state_dir, config_path.parent, "[paths].state_dir"),
        ),
        notify=NotifyConfig(
            guild_id=guild_id,
            webhooks=webhooks,
        ),
    )
