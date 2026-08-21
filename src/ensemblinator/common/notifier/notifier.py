import common.persistence.internal_state as internal_state
from scheduler.meta_parser import JobMeta

import tomllib
import json
from pathlib import Path
import requests
import time

# Discord message text limit is 2000 chars
MESSAGE_BUDGET = 1950
# Discord attachment size limit is 10MB
ATTACHMENT_BUDGET = int(9.5 * 1024 * 1024)

class Notifier:
    def __init__(self, config_dir: Path):
        config_path = config_dir / "notify.toml"
        if not config_path.exists():
            raise FileNotFoundError(f"Missing notification config file: {config_path}")

        with open(config_path, "rb") as f:
            self._config = tomllib.load(f)

        webhooks = self._config.get("webhooks", {})
        if "errors" not in webhooks:
            raise ValueError(f"'errors' webhook is always required in notification config file: {config_path}")
        if "guild_id" not in self._config:
            raise ValueError(f"'guild_id' is always required in notification config file: {config_path}")

    def _post(
        self,
        channel: str,
        content: str,
        ping: bool = False,
        attachment: bytes | None = None,
    ) -> str | None:
        url = self._config["webhooks"][channel]

        payload = {
            "content": content,
            "allowed_mentions": { "parse": ["everyone"] if ping else [] }
        }

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
        except requests.RequestException:
            print("warning: failed to deliver message to errors channel")

    def _report_failure(self, message: str):
        print(f"warning: {message}")
        self._post_errors(f"Notification failure: {message}\n\n@everyone")

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

    def _generate_message(self, name: str | None, exit_code: int, output: str, duration: float) -> str:
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
        if interval <= 0: return False

        now = time.time()
        prev_str = internal_state.state_get(job_id, "prev_heartbeat")

        if now - float(prev_str if prev_str else 0) < interval:
            return False

        internal_state.state_set(job_id, "prev_heartbeat", str(now))
        return True

    def _send_error(self, job_id: str, exit_code: int, consecutive_failures_required: int) -> bool:
        if consecutive_failures_required <= 1:
            return exit_code != 0

        if exit_code == 0:
            internal_state.state_set(job_id, "consecutive_failures", str(0))
            return False
        
        prev_str = internal_state.state_get(job_id, "consecutive_failures")
        prev = int(prev_str) if prev_str else 0
        cur = prev + 1
        internal_state.state_set(job_id, "consecutive_failures", str(cur))
        return cur >= consecutive_failures_required

    def channel_exists(self, channel: str) -> bool:
        return channel in self._config["webhooks"]

    def notify(
        self,
        channels: str | list[str],
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
                message = f"{message}\n```{log_text}```"
            else:
                message = f"{message} Log file attached."
                attachment = self._build_log_attachment(log_text)

        if isinstance(channels, str):
            channels = [channels]

        links = []
        for channel in set(channels):
            try:
                link = self._post(channel, message, attachment=attachment)
                if error and link:
                    links.append(link)
            except KeyError:
                self._report_failure(f"no webhook configured for channel '{channel}'")
            except requests.RequestException:
                self._report_failure(f"failed to deliver message to channel '{channel}'")

        if error:
            self._post_errors(f"{' '.join(links)} @everyone" if links else f"{message}\n\n@everyone", attachment=(None if links else attachment))

    def notify_job_complete(self, meta: JobMeta, exit_code: int, output: str, duration: float):
        if meta.notify is None:
            return

        be_quiet = meta.notify.quiet_success and exit_code == 0 and output == ""
        send_heartbeat = be_quiet and self._heartbeat_due(meta.job_id, meta.notify.heartbeat_interval)

        send_error = self._send_error(meta.job_id, exit_code, meta.notify.consecutive_failures)

        if (not be_quiet) or send_heartbeat:
            message = self._generate_message(meta.name, exit_code, output, duration)
            self.notify(meta.notify.channels, message, send_error, output)

_notifier_instance: Notifier | None = None

def init_notifier(notifier: Notifier):
    global _notifier_instance
    _notifier_instance = notifier

def get() -> Notifier:
    if _notifier_instance is None:
        raise RuntimeError("Notifier not initialized")
    return _notifier_instance
