import os
import paramiko


def resolve_ssh_host(host: str) -> tuple[str, str | None, str | None]:
    """Resolve SSH config alias to real hostname, user, and keyfile."""
    config_path = os.path.expanduser("~/.ssh/config")

    if not os.path.exists(config_path):
        return host, None, None

    ssh_config = paramiko.SSHConfig()
    with open(config_path) as f:
        ssh_config.parse(f)

    host_config = ssh_config.lookup(host)

    hostname = host_config.get("hostname", host)
    user = host_config.get("user")
    identityfile = host_config.get("identityfile", [None])[0]

    return hostname, user, identityfile
