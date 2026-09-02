import logging
import sys
import time

from ensemblinator.notifier import notifier


class StreamFormatter(logging.Formatter):
    converter = time.gmtime

    def format(self, record):
        base = super().format(record)
        log_text = getattr(record, "log_text", None)
        if log_text:
            base = f"{base}\n{log_text}"
        return base


class NotifierErrorHandler(logging.Handler):
    def emit(self, record):
        if record.levelno < logging.ERROR:
            return
        try:
            message = self.format(record)
            log_text = getattr(record, "log_text", None)
            notifier.get().notify(None, message, error=True, log_text=log_text)
        except RuntimeError:
            logging.getLogger("ensemblinator").warning(
                "notifier not yet initialized: failed to deliver error notification"
            )
        except Exception:  # noqa: BLE001 - raising any exceptions here will break logging in bad ways
            logging.getLogger("ensemblinator").warning("failed to deliver error notification")


def configure_logging(level=logging.INFO):
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(
        StreamFormatter(
            "%(asctime)s [%(levelname)s] [ensemblinator]: %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"
        )
    )

    notify_handler = NotifierErrorHandler()
    notify_handler.setFormatter(logging.Formatter("[ensemblinator]: %(message)s"))

    root = logging.getLogger("ensemblinator")
    root.setLevel(level)
    root.addHandler(stream_handler)
    root.addHandler(notify_handler)
