import logging
import os
import paramiko

logger = logging.getLogger(__name__)


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


class SSHConnection:
    """SSH connection manager."""

    host: str
    user: str | None
    _client: paramiko.SSHClient | None

    def __init__(self, host: str, user: str | None = None) -> None:
        """Initialize SSH connection.

        Args:
            host: SSH host alias from ~/.ssh/config or IP/hostname
            user: SSH username (default: None, uses SSH config or falls back to 'root')
        """
        self.host = host
        self.user = user
        self._client = None
        self.connect()

    def connect(self) -> None:
        """Establish SSH connection using SSH keys and agent."""
        # Resolve SSH config alias to actual hostname
        hostname, config_user, keyfile = resolve_ssh_host(self.host)

        # Priority: explicit user > SSH config user > default 'root'
        username = self.user or config_user or "root"

        logger.info(f"Connecting to {self.host} (resolved: {hostname}) as {username}")
        logger.info(f"Using key file: {keyfile}")
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=hostname,
            username=username,
            key_filename=keyfile,
            allow_agent=True,
            look_for_keys=True,
        )
        logger.info("SSH connection established")

    def run_command(self, command: str, check: bool = True) -> tuple[str, int]:
        """Run SSH command. Returns (output, exit_code).

        Args:
            command: Shell command to execute
            check: If True, raise exception on non-zero exit code

        Returns:
            Tuple of (stdout output, exit code)

        Raises:
            RuntimeError: If check=True and command returns non-zero exit code
        """
        if not self._client:
            raise RuntimeError("SSH client not connected")

        logger.debug(f"Running command: {command}")
        _, stdout, stderr = self._client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8").strip()
        error = stderr.read().decode("utf-8").strip()
        logger.debug(f"Command exit code: {exit_code}")

        if check and exit_code != 0:
            logger.error(f"Command failed: {command} (exit code {exit_code})")
            raise RuntimeError(
                f"Command failed with exit code {exit_code}: {command}\n"
                f"Error: {error}\n"
                f"Output: {output}"
            )

        # Return combined output if there's error output
        full_output = output if not error else f"{output}\n{error}".strip()
        return full_output, exit_code

    def close(self) -> None:
        """Close SSH connection."""
        if self._client:
            self._client.close()
            self._client = None

    def ensure_swap(self, size_gb: int = 2) -> None:
        """Create swap file if not already present.

        Args:
            size_gb: Swap file size in GB (default: 2)

        Raises:
            RuntimeError: If swap creation fails
        """
        # Check if swap is already enabled
        output, _ = self.run_command("swapon --show", check=False)

        if output.strip():
            logger.info("Swap already exists")
            return

        # Create swap file
        logger.info(f"Creating {size_gb}GB swap file")
        self.run_command(f"fallocate -l {size_gb}G /swapfile", check=True)
        self.run_command("chmod 600 /swapfile", check=True)
        self.run_command("mkswap /swapfile", check=True)
        self.run_command("swapon /swapfile", check=True)

        # Add to fstab only if not already present (idempotent)
        self.run_command(
            "grep -q '^/swapfile ' /etc/fstab || "
            "echo '/swapfile none swap sw 0 0' >> /etc/fstab",
            check=True,
        )

        logger.info(f"Swap file created successfully: {size_gb}GB")
