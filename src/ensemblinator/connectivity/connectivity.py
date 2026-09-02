import socket

_TARGETS = [("1.1.1.1", 53), ("8.8.8.8", 53)]


def has_connectivity(timeout=2.0) -> bool:
    for host, port in _TARGETS:
        try:
            socket.create_connection((host, port), timeout=timeout).close()
            return True
        except OSError:
            pass
    return False
