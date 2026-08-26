import logging
import sys
import time

class UTCFormatter(logging.Formatter):
    converter = time.gmtime

def configure_logging(level=logging.INFO):
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(UTCFormatter("%(asctime)s [%(levelname)s] [ensemblinator]: %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"))

    root = logging.getLogger("ensemblinator")
    root.setLevel(level)
    root.addHandler(handler)