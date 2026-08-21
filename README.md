# ensemblinator

Job orchestrator and API manager

## Development

    python3 -m venv venv
    source venv/bin/activate
    pip install -e ".[dev]"
    pytest

To run against a test config:

    ensemblinator --config examples/ensemblinator.toml
