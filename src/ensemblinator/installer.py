import subprocess
from pathlib import Path

DEFAULT_CONFIG = """[paths]
# May be absolute, or relative to the folder this file is in
jobs_dir = "./path/to/jobs/dir"
state_dir = "./path/to/state/dir"

[notify]
# The server ID of the Discord server notifications will be sent to
guild_id = "1234567890"

[notify.webhooks]
# Webhooks that send messages in the corresponding channel
errors = "https://discord.com/api/webhooks/..." # REQUIRED
my-channel = "https://discord.com/api/webhooks/..."
"""

DEFAULT_SERVICE_TEMPLATE = """[Unit]
Description=ensemblinator job orchestrator
StartLimitIntervalSec=600
StartLimitBurst=3

[Service]
ExecStart={bin_path} --config {config_file}
Restart=on-failure
RestartSec=5
TimeoutStopSec=60
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
"""


def install():
    print("Installing ensemblinator...")
    home = Path.home()

    # Fixed, set by pipx
    bin_path = home / ".local" / "bin" / "ensemblinator"

    config_dir = home / ".config" / "ensemblinator"
    service_dir = home / ".config" / "systemd" / "user"
    for d in (config_dir, service_dir):
        d.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / "ensemblinator.toml"
    if not config_file.exists():
        config_file.write_text(DEFAULT_CONFIG)
        print(f"Wrote starter config to {config_file} - edit it before starting the service.")
    else:
        print(f"Existing config found at {config_file} not changed.")

    unit_file = service_dir / "ensemblinator.service"
    if not unit_file.exists():
        unit_file.write_text(
            DEFAULT_SERVICE_TEMPLATE.format(bin_path=bin_path, config_file=config_file)
        )
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    else:
        print(f"Existing systemd unit file found at {unit_file} not changed.")

    print("Installation complete. Next steps:")
    print("  loginctl enable-linger $USER   # so the service survives logout")
    print("  systemctl --user enable --now ensemblinator")
