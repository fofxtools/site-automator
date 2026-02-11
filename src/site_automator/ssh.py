import logging
import os
import subprocess
from pathlib import Path

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

    def upload_file(self, local_path: Path | str, remote_path: str) -> None:
        """Upload a file to the remote server using SFTP.

        Args:
            local_path: Path to the local file
            remote_path: Destination path on the remote server

        Raises:
            RuntimeError: If SSH client is not connected
            FileNotFoundError: If local file doesn't exist
        """
        if not self._client:
            raise RuntimeError("SSH client not connected")

        local_path = Path(local_path)
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        logger.info(f"Uploading {local_path} to {remote_path}")

        # Ensure remote directory exists
        remote_dir = os.path.dirname(remote_path)
        if remote_dir:
            self.run_command(f"mkdir -p {remote_dir}", check=True)

        # Upload file using SFTP
        sftp = self._client.open_sftp()
        try:
            sftp.put(str(local_path), remote_path)
            logger.info(f"File uploaded successfully: {remote_path}")
        finally:
            sftp.close()

    def upload_directory_rsync(
        self,
        local_dir: Path | str,
        remote_dir: str,
        *,
        delete: bool = False,
        exclude: list[str] | None = None,
    ) -> None:
        """Upload a directory to the remote server using rsync over SSH.

        Syncs the contents of local_dir to remote_dir. If local_dir is empty
        and delete=True, all remote files will be deleted (exact sync).

        Args:
            local_dir: Path to the local directory
            remote_dir: Destination path on the remote server
            delete: If True, delete remote files not present locally (default: False)
            exclude: Optional list of exclude patterns (e.g., [".git/", "*.tmp"])

        Raises:
            RuntimeError: If rsync command fails
            FileNotFoundError: If local directory doesn't exist
        """
        import shlex

        local_dir = Path(local_dir)
        if not local_dir.exists():
            raise FileNotFoundError(f"Local directory not found: {local_dir}")
        if not local_dir.is_dir():
            raise ValueError(f"Path is not a directory: {local_dir}")

        logger.info(f"Uploading directory {local_dir} to {remote_dir} via rsync")

        # Ensure remote directory exists
        self.run_command(f"mkdir -p {shlex.quote(remote_dir)}", check=True)

        # Resolve SSH config for rsync
        hostname, config_user, keyfile = resolve_ssh_host(self.host)
        username = self.user or config_user or "root"

        # Build rsync command
        rsync_cmd = [
            "rsync",
            "-avz",  # archive, verbose, compress
            "--stats",  # Show transfer statistics
        ]

        # Add delete flag if requested
        if delete:
            rsync_cmd.append("--delete")

        # Add exclude patterns
        if exclude:
            for pattern in exclude:
                rsync_cmd.extend(["--exclude", pattern])

        # Build SSH command for rsync
        ssh_cmd = ["ssh"]
        if keyfile:
            ssh_cmd.extend(["-i", keyfile])

        rsync_cmd.extend(["-e", " ".join(ssh_cmd)])

        # Add trailing slash to sync directory contents (not the directory itself)
        local_path = str(local_dir).rstrip("/") + "/"
        remote_path = f"{username}@{hostname}:{shlex.quote(remote_dir)}"

        rsync_cmd.extend([local_path, remote_path])

        # Execute rsync
        logger.debug(f"Rsync command: {' '.join(rsync_cmd)}")
        try:
            result = subprocess.run(
                rsync_cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.debug(f"Rsync output:\n{result.stdout}")
            logger.info(f"Directory uploaded successfully: {remote_dir}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Rsync failed: {e.stderr}")
            raise RuntimeError(
                f"Rsync failed with exit code {e.returncode}\n"
                f"Command: {' '.join(rsync_cmd)}\n"
                f"Error: {e.stderr}"
            ) from e

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

    def ensure_git_safe_directory(self) -> None:
        """Configure git to allow WordOps to manage site configs.

        Git blocks operations in repositories owned by another user.
        WordOps creates site config repos as www-data but runs commands as root,
        which can trigger "dubious ownership" errors.

        Set safe.directory='*' at the system level so automation can
        operate on WordOps-managed repositories without git failures.

        This should be run once during initial server setup.
        """
        logger.info("Configuring git safe.directory for WordOps")
        self.run_command("git config --system --add safe.directory '*'", check=True)
        logger.info("Git safe.directory configured")
