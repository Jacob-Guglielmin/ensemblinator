import logging
import sys
import traceback

_logger = logging.getLogger(__name__)


def handle_uncaught(exc_type, exc_value, exc_tb):
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    notify_crash_text(tb_text)
    sys.__excepthook__(exc_type, exc_value, exc_tb)  # preserve default behavior


def handle_thread_exception(args):
    tb_text = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    notify_crash_text(tb_text, f"thread {args.thread.name}")


def handle_job_error(event):
    exc = event.exception
    tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    notify_crash_text(tb_text, f"job {event.job_id}")


def notify_crash(exc: BaseException, context: str = "") -> None:
    tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    notify_crash_text(tb_text, context)


def notify_crash_text(tb_text: str, context: str = "") -> None:
    label = f" ({context})" if context else ""
    _logger.error(f"unknown unhandled exception{label}.", extra={"log_text": tb_text})
