import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

from ensemblinator.persistence import internal_state
from ensemblinator.scheduler.meta_parser import JobMeta

_logger = logging.getLogger(__name__)

# Discord message text limit is 2000 chars
MESSAGE_BUDGET = 1925
# Discord attachment size limit is 10MB
ATTACHMENT_BUDGET = int(9.5 * 1024 * 1024)


class Notifier:
    def __init__(self, config: dict, state_dir: Path):
        self._config = config
        self._state_dir = state_dir

        self._pending: list[tuple[str, str, bytes | None, bool, float]] = []

        webhooks = self._config.get("webhooks", {})
        if "errors" not in webhooks:
            raise ValueError(
                "'errors' webhook is always required in notify config in ensemblinator.toml"
            )
        if "guild_id" not in self._config:
            raise ValueError("'guild_id' is always required in notify config in ensemblinator.toml")

    def _post(
        self,
        channel: str,
        content: str,
        ping: bool = False,
        attachment: bytes | None = None,
    ) -> str | None:
        url = self._config["webhooks"][channel]

        payload = {"content": content, "allowed_mentions": {"parse": ["everyone"] if ping else []}}

        if attachment:
            resp = requests.post(
                url,
                params={"wait": "true"},
                data={"payload_json": json.dumps(payload)},
                files={"files[0]": ("output.log", attachment)},
                timeout=10,
            )
        else:
            resp = requests.post(url, params={"wait": "true"}, json=payload, timeout=10)

        resp.raise_for_status()
        body = resp.json()

        msg_id, chan_id = body.get("id"), body.get("channel_id")
        if msg_id and chan_id:
            return f"https://discord.com/channels/{self._config['guild_id']}/{chan_id}/{msg_id}"
        return None

    def _post_errors(self, content: str, attachment: bytes | None = None):
        try:
            self._post("errors", content, ping=True, attachment=attachment)
        except requests.HTTPError as e:
            _logger.warning(
                f"HTTP error while delivering message to errors channel: {e}; will not retry"
            )
        except requests.RequestException:
            self._pending.append(("errors", content, attachment, True, time.time()))
            _logger.warning("failed to deliver message to errors channel; queued for retry")

    def _report_failure(self, message: str):
        _logger.warning(message)
        self._post_errors(f"[ensemblinator]: notification failure: {message}\n\n@everyone")

    def _build_log_attachment(self, content: str) -> bytes:
        data = content.encode()
        if len(data) > ATTACHMENT_BUDGET:
            data = data[-ATTACHMENT_BUDGET:]
            # the slice above may land mid-character on a multi-byte UTF-8
            # sequence at the very start; clean that up rather than leaving
            # a malformed leading byte in the file
            data = data.decode(errors="replace").encode()
            data = b"... [truncated, log too large] ...\n" + data
        return data

    def _generate_message(
        self, name: str | None, exit_code: int, output: str, duration: float
    ) -> str:
        label = f"{name}: " if name else ""
        if exit_code == 0:
            message = f"{label}Completed successfully in {self._format_duration(duration)}"
        else:
            message = f"{label}Failed (exit code {exit_code}) in {self._format_duration(duration)}"

        if output == "":
            message = f"{message} with no output."
        else:
            message = f"{message}."

        return message

    def _format_duration(self, duration: float) -> str:
        seconds = round(duration)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    def _heartbeat_due(self, job_id: str, interval: float) -> bool:
        if interval <= 0:
            return False

        now = time.time()
        prev_str = internal_state.state_get(self._state_dir, job_id, "prev_heartbeat")

        if now - float(prev_str if prev_str else 0) < interval:
            return False

        internal_state.state_set(self._state_dir, job_id, "prev_heartbeat", str(now))
        return True

    def _send_error(self, job_id: str, exit_code: int, consecutive_failures_required: int) -> bool:
        if consecutive_failures_required <= 1:
            return exit_code != 0

        if exit_code == 0:
            internal_state.state_set(self._state_dir, job_id, "consecutive_failures", str(0))
            return False

        prev_str = internal_state.state_get(self._state_dir, job_id, "consecutive_failures")
        prev = int(prev_str) if prev_str else 0
        cur = prev + 1
        internal_state.state_set(self._state_dir, job_id, "consecutive_failures", str(cur))
        return cur >= consecutive_failures_required

    def channel_exists(self, channel: str) -> bool:
        return channel in self._config["webhooks"]

    def flush_pending(self):
        while self._pending:
            channel, message, attachment, ping, queue_time = self._pending[0]

            ts = datetime.fromtimestamp(queue_time, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
            catchup_message = f"(catchup: {ts} UTC)\n{message}"

            try:
                self._post(channel, catchup_message, ping=ping, attachment=attachment)
                self._pending.pop(0)
            except requests.HTTPError as e:
                self._pending.pop(0)
                _logger.warning(
                    f"HTTP error while flushing queued notification, will not retry: {e}"
                )
            except requests.RequestException:
                _logger.warning(
                    "failed to flush queued notification, will retry at next opportunity"
                )
                return

    def notify(
        self,
        channels: str | list[str] | None,
        message: str,
        error: bool = False,
        log_text: str | None = None,
    ) -> None:
        """
        Send `message` to Discord channels by name as configured in notify.toml.

        If `error=True`, also post a reference to the message in #errors, along with
        a ping to @everyone.
        """
        attachment: bytes | None = None
        if log_text:
            if len(log_text) + len(message) <= MESSAGE_BUDGET and "```" not in log_text:
                message = f"{message}\n```\n{log_text}\n```"
            else:
                message = f"{message} Log file attached."
                attachment = self._build_log_attachment(log_text)

        if channels is None:
            channels = []
        elif isinstance(channels, str):
            channels = [channels]

        links = []
        for channel in set(channels):
            try:
                link = self._post(channel, message, attachment=attachment)
                if error and link:
                    links.append(link)
            except KeyError:
                self._report_failure(f"no webhook configured for channel '{channel}'")
            except requests.HTTPError as e:
                self._report_failure(
                    f"HTTP error while delivering message to channel '{channel}', will not retry: {e}"
                )
            except requests.RequestException:
                self._pending.append((channel, message, attachment, False, time.time()))
                _logger.warning(
                    f"failed to deliver message to channel '{channel}'; queued for retry"
                )

        if error:
            self._post_errors(
                f"{' '.join(links)} @everyone" if links else f"{message}\n\n@everyone",
                attachment=(None if links else attachment),
            )

    def notify_job_complete(self, meta: JobMeta, exit_code: int, output: str, duration: float):
        if meta.notify is None:
            return

        be_quiet = meta.notify.quiet_success and exit_code == 0 and output == ""
        send_heartbeat = be_quiet and self._heartbeat_due(
            meta.job_id, meta.notify.heartbeat_interval
        )

        send_error = self._send_error(meta.job_id, exit_code, meta.notify.consecutive_failures)

        if (not be_quiet) or send_heartbeat:
            message = self._generate_message(meta.name, exit_code, output, duration)
            self.notify(meta.notify.channels, message, send_error, output)

    def notify_job_skipped(self, meta: JobMeta, reason: str):
        if meta.notify is None:
            return

        message = f"{meta.name + ': ' if meta.name else ''}Skipped: {reason}."
        self.notify(meta.notify.channels, message, error=True)


_notifier_instance: Notifier | None = None


def init_notifier(notifier: Notifier):
    global _notifier_instance
    _notifier_instance = notifier


def get() -> Notifier:
    if _notifier_instance is None:
        raise RuntimeError("Notifier not initialized")
    return _notifier_instance
