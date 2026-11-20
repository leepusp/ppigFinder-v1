"""Strict-host-key SSH/SFTP transport; no scheduler or GPU execution.

Paramiko is optional, imported only when connecting. Credentials may be passed
in memory, never written to profile files, logs or the Git repository.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import getpass
import hashlib
import os
from pathlib import Path
import posixpath
import re
import shlex
import stat
import tempfile
import uuid

from .profiles import RemoteProfile, safe_relative_path


class RemoteConnectionError(RuntimeError):
    """Connection/configuration failure with actionable context."""


@dataclass(frozen=True)
class TransferReceipt:
    local_path: str
    remote_path: str
    remote_result_dir: str
    sha256: str
    bytes_sent: int

    def as_dict(self) -> dict:
        return asdict(self)


def _hash_local(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_sftp(sftp, path: str) -> str:
    digest = hashlib.sha256()
    with sftp.open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_filename(path: Path, sha: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]", "_", path.stem).strip("._-")[:72] or "input"
    suffix = re.sub(r"[^A-Za-z0-9.]", "", path.suffix.lower())[:12]
    return f"{stem}_{sha[:12]}{suffix}"


def preview_af3_wrapper(profile: RemoteProfile, receipt: TransferReceipt, job_name: str) -> str:
    """Return a *display-only* local-executor command, never submit it.

    It is unsafe to run this on an HPC login node. The caller must first obtain
    a site-approved compute allocation or use a separate scheduler adapter.
    """
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", job_name):
        raise ValueError("AF3 job name contains unsafe characters")
    if not receipt.remote_path.startswith("/") or not receipt.remote_result_dir.startswith("/"):
        raise ValueError("Only absolute verified remote paths are supported")
    return shlex.join([
        profile.af3_wrapper, "--json-path", receipt.remote_path,
        "--job-name", job_name, "--workdir", receipt.remote_result_dir,
        "--stage", "all", "--executor", "local",
    ])


class SSHTransport:
    """Short-lived SSH session and restricted, checksum-verified SFTP methods."""

    def __init__(self, profile: RemoteProfile, *, password: str | None = None, timeout: float = 12):
        self.profile = profile
        self._password = password
        self.timeout = timeout
        self._client = None
        self._sftp = None
        self._root = None
        self._home = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_):
        self.close()

    def connect(self) -> "SSHTransport":
        try:
            import paramiko
        except ImportError as exc:
            raise RemoteConnectionError("Paramiko is not installed. Use pip install 'ppigfinder[recommended]'.") from exc
        if self._client is not None:
            return self
        config_path = Path.home() / ".ssh" / "config"
        options: dict = {}
        if config_path.is_file():
            ssh_config = paramiko.SSHConfig()
            with config_path.open(encoding="utf-8") as stream:
                ssh_config.parse(stream)
            options = ssh_config.lookup(self.profile.host)
        if "proxycommand" in options or "proxyjump" in options:
            raise RemoteConnectionError(
                "This transport version does not support ProxyJump/ProxyCommand. "
                "Use a direct SSH profile; no tunnel is created implicitly."
            )
        hostname = options.get("hostname") or self.profile.host
        username = self.profile.username or options.get("user") or getpass.getuser()
        port = self.profile.port or int(options.get("port") or 22)
        identities = options.get("identityfile") or []
        if isinstance(identities, str):
            identities = [identities]
        identities = [str(Path(value).expanduser()) for value in identities]
        client = paramiko.SSHClient()
        client.load_system_host_keys()  # ~/.ssh/known_hosts, including hashed entries
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        try:
            client.connect(
                hostname=hostname, port=port, username=username,
                password=self._password,
                # An entered password is for SSH login, not decryption of
                # unrelated encrypted keys listed in ~/.ssh/config.
                key_filename=(identities or None) if self._password is None else None,
                allow_agent=self._password is None,
                look_for_keys=self._password is None,
                timeout=self.timeout,
                auth_timeout=self.timeout, banner_timeout=self.timeout,
            )
            sftp = client.open_sftp()
            remote_home = sftp.normalize(".")
            if not remote_home.startswith("/"):
                raise RemoteConnectionError("SFTP did not return an absolute remote home directory")
            self._client, self._sftp = client, sftp
            self._home = remote_home
            self._root = posixpath.join(remote_home, self.profile.remote_subdir)
            self._password = None  # Clear credentials immediately after authentication
            return self
        except Exception as exc:
            client.close()
            if isinstance(exc, RemoteConnectionError):
                raise
            error_type = type(exc).__name__
            raise RemoteConnectionError(
                f"SSH/SFTP failed ({error_type}). Check credentials, ~/.ssh/config, "
                "known_hosts fingerprint and host reachability. Unknown host keys are never accepted automatically."
            ) from exc

    def close(self) -> None:
        if self._sftp is not None:
            self._sftp.close()
        if self._client is not None:
            self._client.close()
        self._sftp = self._client = self._root = self._home = None
        self._password = None

    @property
    def remote_root(self) -> str:
        if self._root is None:
            raise RemoteConnectionError("Not connected")
        return self._root

    def _sftp_required(self):
        if self._sftp is None:
            raise RemoteConnectionError("Not connected")
        return self._sftp

    def _path(self, relative: str) -> str:
        return posixpath.join(self.remote_root, safe_relative_path(relative))

    def _ensure_folder(self, path: str) -> None:
        sftp = self._sftp_required()
        # Never create or follow symlinked project directories.
        home = self._home
        if home is None:
            raise RemoteConnectionError("Not connected")
        if not (path == home or path.startswith(home.rstrip("/") + "/")):
            raise ValueError("Remote folder is outside the approved home subtree")
        current = home
        for part in path[len(home):].strip("/").split("/"):
            if not part:
                continue
            current = posixpath.join(current, part)
            try:
                attrs = sftp.lstat(current)
            except OSError as exc:
                if getattr(exc, "errno", None) != 2:
                    raise
                sftp.mkdir(current, mode=0o700)
                attrs = sftp.lstat(current)
            if not stat.S_ISDIR(attrs.st_mode) or stat.S_ISLNK(attrs.st_mode):
                raise ValueError(f"Remote project component is not a real directory: {current}")

    def test(self) -> dict:
        """Read-only connectivity check; no command or scheduler invocation."""
        self._sftp_required()
        return {"profile": self.profile.name, "host": self.profile.host,
                "remote_root": self.remote_root, "status": "SSH_SFTP_CONNECTED"}

    def upload_file(self, local_path: str | Path, *, destination: str = "inputs", max_bytes: int = 64 * 1024 * 1024) -> TransferReceipt:
        """Upload into dedicated project root; verify remote SHA-256 by SFTP readback."""
        sftp = self._sftp_required()
        path = Path(local_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        size = path.stat().st_size
        if size == 0 or size > max_bytes:
            raise ValueError(f"Upload must be 1..{max_bytes} bytes")
        relative_dir = safe_relative_path(destination)
        dest_folder = self._path(relative_dir)
        local_sha = _hash_local(path)
        name = _safe_filename(path, local_sha)
        destination_path = posixpath.join(dest_folder, name)
        results = self._path("results/" + name.rsplit(".", 1)[0])
        self._ensure_folder(dest_folder)
        try:
            sftp.lstat(destination_path)
        except OSError as exc:
            if getattr(exc, "errno", None) != 2:
                raise
        else:
            if _hash_sftp(sftp, destination_path) != local_sha:
                raise ValueError("Remote filename collision with different content")
            return TransferReceipt(str(path), destination_path, results, local_sha, size)
        temp_path = posixpath.join(dest_folder, ".upload_" + uuid.uuid4().hex + ".part")
        try:
            sftp.put(str(path), temp_path, confirm=True)
            if _hash_sftp(sftp, temp_path) != local_sha:
                raise ValueError("Remote SHA-256 mismatch after upload")
            sftp.rename(temp_path, destination_path)
        finally:
            try:
                sftp.remove(temp_path)
            except OSError:
                pass
        return TransferReceipt(str(path), destination_path, results, local_sha, size)

    def download_file(self, remote_relative_path: str, local_path: str | Path) -> dict:
        """Download one project artifact; validate SFTP SHA-256 before atomic replace."""
        sftp = self._sftp_required()
        remote = self._path(remote_relative_path)
        destination = Path(local_path).expanduser().resolve()
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite local artifact: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        expected_sha = _hash_sftp(sftp, remote)
        fd, temp = tempfile.mkstemp(prefix=".ppig-download-", dir=str(destination.parent))
        os.close(fd)
        try:
            sftp.get(remote, temp)
            if _hash_local(Path(temp)) != expected_sha:
                raise ValueError("Downloaded file checksum does not match SFTP source")
            os.replace(temp, destination)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return {"local_path": str(destination), "remote_path": remote, "sha256": expected_sha}
