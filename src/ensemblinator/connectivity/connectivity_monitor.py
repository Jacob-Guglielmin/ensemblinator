import threading
from collections.abc import Callable

from ensemblinator.connectivity.connectivity import has_connectivity


class ConnectivityMonitor:
    def __init__(
        self,
        interval: float,
        consecutive_tests: int,
        on_transition: Callable[[bool], None] | None = None,
        on_up_periodic: Callable[[], None] | None = None,
    ):
        self._interval = interval
        self._consecutive_tests = consecutive_tests
        self._on_transition = on_transition
        self._on_up_periodic = on_up_periodic
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self):
        network_up = has_connectivity()
        consecutive = 0
        while not self._stop.wait(self._interval):
            up_now = has_connectivity()

            if up_now and self._on_up_periodic is not None:
                self._on_up_periodic()

            if up_now == network_up:
                consecutive = 0
                continue

            consecutive += 1
            if consecutive < self._consecutive_tests:
                continue

            network_up = up_now
            consecutive = 0

            if self._on_transition is not None:
                self._on_transition(up_now)
