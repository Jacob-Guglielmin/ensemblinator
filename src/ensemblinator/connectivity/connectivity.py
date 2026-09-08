import socket
import subprocess
import time

_TARGETS = [("1.1.1.1", 53), ("8.8.8.8", 53)]


def has_connectivity(timeout=2.0) -> bool:
    for host, port in _TARGETS:
        try:
            socket.create_connection((host, port), timeout=timeout).close()
            return True
        except OSError:
            pass
    return False


def wait_for_ntp_sync(timeout: float = 120, poll_interval: float = 2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip() == "yes":
            return True
        time.sleep(poll_interval)
    return False
