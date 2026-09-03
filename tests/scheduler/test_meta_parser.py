from collections.abc import Callable  # noqa: F401 - used in type annotations only
from pathlib import Path

import pytest

from ensemblinator.notifier import notifier
from ensemblinator.scheduler.meta_parser import MetaParseError, parse_job_header
from ensemblinator.scheduler.types import (
    CronSchedule,
    EventSchedule,
    JobMeta,  # noqa: F401 - used in type annotations only
    JobRequirement,
    TriggerEvent,
)


@pytest.fixture(autouse=True)
def fake_notifier(monkeypatch):
    fake = type("Fake", (), {"channel_exists": lambda self, c: c in ("general", "errors")})()
    monkeypatch.setattr(notifier, "get", lambda: fake)
    return fake


@pytest.fixture
def parsed_raw_text(tmp_path):
    def _parse(content: str | list[str], relative_path: Path = Path("./job.sh")):
        path = tmp_path / relative_path
        content = content if isinstance(content, list) else [content]
        path.write_text("\n".join(content))
        return parse_job_header(path, tmp_path)

    return _parse


DEFAULT_HEADER = {"job": "test job", "schedule": "cron: * * * * *"}


@pytest.fixture
def parsed(tmp_path):
    def _parse(
        directives: dict[str, str | list[str]] | None = None, relative_path: Path = Path("./job.sh")
    ):
        header: dict[str, str | list[str]] = {**DEFAULT_HEADER, **(directives or {})}
        lines = []
        for key, value in header.items():
            if value is None:
                continue
            values = value if isinstance(value, list) else [value]
            for v in values:
                lines.append(f"# @{key} {v}")
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines))
        return parse_job_header(path, tmp_path)

    return _parse


class TestJobParsing:
    @pytest.mark.parametrize(
        "non_job_content",
        [
            "",
            ["# @schedule cron: * * * * *", "# @timeout 30"],
            ["foo", "# @job"],
        ],
    )
    def test_non_jobs_none(self, parsed_raw_text, non_job_content):
        assert parsed_raw_text(non_job_content) is None

    @pytest.mark.parametrize("comment_prefix", ["#", "//"])
    def test_comment_types(self, parsed_raw_text, comment_prefix):
        assert (
            parsed_raw_text([f"{comment_prefix} @job", f"{comment_prefix} @schedule network: up"])
            is not None
        )

    @pytest.mark.parametrize("line", ["", "     ", "# foo"])
    def test_interspersed_lines(self, parsed_raw_text, line):
        assert parsed_raw_text([line, "# @job", "# @schedule network: up"]) is not None
        assert parsed_raw_text(["# @schedule network: up", line, "# @job"]) is not None

    def test_job_id(self, parsed):
        assert (
            parsed(relative_path=Path("./complicated/path/../to/jobfile.sh")).job_id
            == "complicated/to/jobfile.sh"
        )


class TestDirectiveShape:
    def test_unknown_directive_raises(self, parsed):
        with pytest.raises(MetaParseError, match="unknown"):
            parsed({"not-a-directive": "foo"})

    def test_missing_required_directive_raises(self, parsed):
        with pytest.raises(MetaParseError, match="missing required"):
            parsed({"schedule": None})

    def test_multiple_singular_directive_raises(self, parsed):
        with pytest.raises(MetaParseError, match="multiple"):
            parsed({"job": ["a", "b"]})

    def test_flag_with_content_raises(self, parsed):
        with pytest.raises(MetaParseError, match="flag"):
            parsed({"notify.quiet-success": "foo"})

    def test_flag_true_or_false(self, parsed):
        assert (
            parsed({"notify.channel": "general", "notify.quiet-success": ""}).notify.quiet_success
            is True
        )
        assert (
            parsed({"notify.channel": "general", "notify.quiet-success": None}).notify.quiet_success
            is False
        )

    def test_defaults_applied(self, parsed):
        meta = parsed({"timeout": None})
        assert isinstance(meta.timeout, float)
        assert meta.timeout > 0

    def test_multi_directive_accepts_multi(self, parsed):
        meta = parsed({"schedule": ["network: up", "system: down", "cron: * * * * *"]})
        assert len(meta.schedules) == 3


class TestDirectiveParsing:
    def test_job(self, parsed):
        assert parsed({"job": "foo"}).name == "foo"
        assert parsed({"job": ""}).name is None

    def test_unknown_schedule(self, parsed):
        with pytest.raises(MetaParseError, match="unknown schedule"):
            parsed({"schedule": "foo: bar"})

    def test_cron_schedule(self, parsed):
        assert parsed({"schedule": "cron: 5,15 4-8/2 * FEB TUE"}).schedules[0] == CronSchedule(
            "5,15 4-8/2 * FEB TUE"
        )

        with pytest.raises(MetaParseError, match="invalid cron"):
            parsed({"schedule": "cron: foo * * * *"})

    def test_event_schedule(self, parsed):
        assert parsed({"schedule": "network: down"}).schedules[0] == EventSchedule(
            TriggerEvent.NETWORK_DOWN
        )
        assert parsed({"schedule": "system: up"}).schedules[0] == EventSchedule(
            TriggerEvent.SYSTEM_UP
        )

        with pytest.raises(MetaParseError, match=r"invalid.*schedule"):
            parsed({"schedule": "network: foo"})

    def test_duplicate_schedule(self, parsed):
        parsed({"schedule": ["network: up", "network: down"]})
        parsed({"schedule": ["cron: 1 2 3 4 5", "cron: 2 2 3 4 5"]})

        with pytest.raises(MetaParseError, match="duplicate"):
            parsed({"schedule": ["cron: 1 2 3 4 5", "network: up", "cron: 1 2 3 4 5"]})

        with pytest.raises(MetaParseError, match="duplicate"):
            parsed({"schedule": ["network: up", "network: up"]})

    @pytest.mark.parametrize("bad_value", ["", "foo", "0", "-1"])
    def test_timeout_invalid(self, parsed, bad_value):
        with pytest.raises(MetaParseError, match="must be"):
            parsed({"timeout": bad_value})

    @pytest.mark.parametrize("good_value", [0.01, 1, 1234.5])
    def test_timeout_valid(self, parsed, good_value):
        assert parsed({"timeout": str(good_value)}).timeout == good_value

    def test_requires_empty(self, parsed):
        assert parsed({"requires": None}).requires == []

    def test_requires_valid(self, parsed):
        meta = parsed({"requires": "network"})
        assert meta.requires == [JobRequirement.NETWORK]

    def test_requires_invalid(self, parsed):
        with pytest.raises(MetaParseError, match="unknown requirement"):
            parsed({"requires": ["network", "not-a-requirement"]})

    def test_notify_channel_invalid(self, parsed):
        with pytest.raises(MetaParseError, match="unknown channel"):
            parsed({"notify.channel": ["general", "not-a-channel"]})

    def test_notify_channel_valid(self, parsed):
        meta = parsed({"notify.channel": ["general", "errors"]})
        assert meta.notify is not None
        assert meta.notify.channels == ["general", "errors"]

    @pytest.mark.parametrize("bad_value", ["", "foo", "-1"])
    def test_notify_heartbeat_interval_invalid(self, parsed, bad_value):
        with pytest.raises(MetaParseError, match="must be"):
            parsed({"notify.channel": "general", "notify.heartbeat-interval": bad_value})

    @pytest.mark.parametrize("good_value", [0, 0.001, 80000.5])
    def test_notify_heartbeat_interval_valid(self, parsed, good_value):
        assert (
            parsed(
                {"notify.channel": "general", "notify.heartbeat-interval": str(good_value)}
            ).notify.heartbeat_interval
            == good_value
        )

    @pytest.mark.parametrize("bad_value", ["", "foo", "0", "10.5", "-1"])
    def test_notify_consecutive_failures_invalid(self, parsed, bad_value):
        with pytest.raises(MetaParseError, match="must be"):
            parsed({"notify.channel": "general", "notify.consecutive-failures": bad_value})

    @pytest.mark.parametrize("good_value", [1, 5])
    def test_notify_consecutive_failures_valid(self, parsed, good_value):
        assert (
            parsed(
                {"notify.channel": "general", "notify.consecutive-failures": str(good_value)}
            ).notify.consecutive_failures
            == good_value
        )


class TestAdditionalRules:
    def test_notify_without_channel(self, parsed):
        with pytest.raises(MetaParseError, match="channel"):
            parsed({"notify.quiet-success": ""})

    def test_no_notify(self, parsed):
        assert parsed().notify is None

    @pytest.mark.parametrize("good_value", [15, 44, 45])
    def test_enforced_system_timeout_valid(self, parsed, good_value):
        assert parsed({"schedule": "system: up", "timeout": str(good_value)}).timeout == good_value

    @pytest.mark.parametrize("bad_value", ["45.001", "55", "3600.0"])
    def test_enforced_system_timeout_invalid(self, parsed, bad_value):
        with pytest.raises(MetaParseError, match="timeout"):
            parsed({"schedule": "system: up", "timeout": bad_value})
