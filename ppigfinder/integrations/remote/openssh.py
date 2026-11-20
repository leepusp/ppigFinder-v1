"""Use local OpenSSH for authentication, and SFTP protocol over its SSH channel.

This adapter delegates authentication and ~/.ssh/config/ProxyJump/known_hosts to
OpenSSH, avoiding Paramiko authentication discrepancies. Paramiko is used ONLY
for SFTP protocol framing over an already-authenticated OpenSSH `-s sftp`
subsystem, not to establish its own SSH connection. The existing protected
SFTP upload/download/sha256 validation code is inherited from SSHTransport.

No remote shell, AF3 inference, scheduler submission, passwords in argv/env,
or saved credentials. Linux/WSL/macOS only; older Paramiko transport retained.
"""
from __future__ import annotations

import os
from pathlib import Path
import select
import shutil
import socket
import subprocess
import tempfile
import threading

from .profiles import RemoteProfile
from .transport import SSHTransport, RemoteConnectionError


# OpenSSH requires an askpass executable for GUI authentication. Only a tiny
# credential-free helper is written to disk. A password is returned once from
# an owner-only Unix socket while the authentication process is in progress.
_ASKPASS_SCRIPT = '''#!/usr/bin/env python3
import os
import socket
import sys
sock = socket.socket(socket.AF_UNIX)
try:
    sock.settimeout(8)
    sock.connect(os.environ["PPIGFINDER_SSH_ASKPASS_SOCKET"])
    with sock:
        data = bytearray()
        while len(data) < 65536:
            part = sock.recv(8192)
            if not part:
                break
            data.extend(part)
    sys.stdout.buffer.write(bytes(data) + b"\\n")
except Exception:
    sys.exit(1)
'''


class _PasswordAskpass:
    """Ephemeral one-shot GUI askpass bridge: secret never placed on disk."""

    def __init__(self, directory: Path, password: str):
        self.socket_path = str(directory / "ask.sock")
        self.helper_path = directory / "askpass.py"
        self._password = password
        self._server = None
        self._thread = None
        self._done = threading.Event()
        self._served = False

    def __enter__(self):
        self.helper_path.write_text(_ASKPASS_SCRIPT, encoding="utf-8")
        self.helper_path.chmod(0o700)
        self._server = socket.socket(socket.AF_UNIX)
        self._server.bind(self.socket_path)
        os.chmod(self.socket_path, 0o600)
        self._server.listen(1)
        self._server.settimeout(0.25)

        def serve():
            while not self._done.is_set() and not self._served:
                try:
                    client, _ = self._server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with client:
                    try:
                        client.sendall(self._password.encode("utf-8"))
                        self._served = True
                    except OSError:
                        break
        self._thread = threading.Thread(target=serve, name="ppig-askpass", daemon=True)
        self._thread.start()
        return self

    def environment(self) -> dict[str, str]:
        return {
            "SSH_ASKPASS": str(self.helper_path),
            "SSH_ASKPASS_REQUIRE": "force",
            "PPIGFINDER_SSH_ASKPASS_SOCKET": self.socket_path,
        }

    def __exit__(self, *_):
        self._done.set()
        self._password = ""
        if self._server:
            self._server.close()
        if self._thread:
            self._thread.join(timeout=2)
        try:
            os.unlink(self.socket_path)
        except FileNotFoundError:
            pass
        self.helper_path.unlink(missing_ok=True)


class _OpenSSHSubprocessChannel:
    """Minimal byte-stream interface accepted by Paramiko SFTPClient.

    It wraps an OpenSSH command running the SFTP subsystem. No second SSH
    authentication is performed by Paramiko.
    """

    def __init__(self, process: subprocess.Popen, *, timeout: float = 90.0):
        self.process = process
        self.timeout = timeout

    def get_name(self) -> str:
        return "ppigfinder-openssh-sftp"

    def recv(self, length: int) -> bytes:
        if self.process.stdout is None:
            raise EOFError("OpenSSH subsystem stdout closed")
        ready, _, _ = select.select([self.process.stdout.fileno()], [], [], self.timeout)
        if not ready:
            raise TimeoutError("Timed out reading OpenSSH SFTP subsystem")
        return os.read(self.process.stdout.fileno(), length)

    def send(self, data: bytes) -> int:
        if self.process.stdin is None:
            raise EOFError("OpenSSH subsystem stdin closed")
        _, ready, _ = select.select([], [self.process.stdin.fileno()], [], self.timeout)
        if not ready:
            raise TimeoutError("Timed out writing to OpenSSH SFTP subsystem")
        return os.write(self.process.stdin.fileno(), data)

    def close(self):
        for stream in (self.process.stdin, self.process.stdout):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)


class OpenSSHTransport(SSHTransport):
    """OpenSSH-authenticated transport, with verified SFTP methods inherited."""

    @staticmethod
    def is_available():
        return os.name == "posix" and shutil.which("ssh") is not None

    def __init__(self, profile: RemoteProfile, *, password: str | None = None, timeout: float = 18):
        super().__init__(profile, password=password, timeout=timeout)
        self._ssh = shutil.which("ssh")
        self._temp = None
        self._socket_path = None
        self._subsystem = None
        self._pipe = None

    def _base_argv(self):
        argv = [self._ssh, "-o", "StrictHostKeyChecking=yes"]
        if self._socket_path:
            argv += ["-o", f"ControlPath={self._socket_path}"]
        return argv

    def _target_args(self):
        args = []
        if self.profile.username:
            args += ["-l", self.profile.username]
        if self.profile.port:
            args += ["-p", str(self.profile.port)]
        return args + [self.profile.host]

    def _start_master(self):
        self._temp = tempfile.TemporaryDirectory(prefix="ppig-ssh-")
        runtime = Path(self._temp.name)
        runtime.chmod(0o700)
        self._socket_path = str(runtime / "master.sock")
        argv = self._base_argv() + ["-o", "ControlMaster=yes", "-o", "ControlPersist=no",
                                    "-o", f"ConnectTimeout={max(3, int(self.timeout))}",
                                    "-o", "ConnectionAttempts=1"]
        if self._password is not None:
            argv += ["-o", "PubkeyAuthentication=no", "-o", "PasswordAuthentication=yes",
                     "-o", "KbdInteractiveAuthentication=yes",
                     "-o", "PreferredAuthentications=password,keyboard-interactive",
                     "-o", "NumberOfPasswordPrompts=1", "-o", "BatchMode=no"]
        else:
            argv += ["-o", "BatchMode=yes"]
        argv += ["-f", "-N", "-M"] + self._target_args()
        env = dict(os.environ)
        env.pop("PPIGFINDER_SSH_ASKPASS_SOCKET", None)
        env.pop("SSH_ASKPASS_REQUIRE", None)
        if self._password is not None:
            with _PasswordAskpass(runtime, self._password) as askpass:
                env.update(askpass.environment())
                result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                        text=True, timeout=self.timeout + 15, env=env, check=False)
        else:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                    text=True, timeout=self.timeout + 15, env=env, check=False)
        self._password = None
        if result.returncode:
            raise RemoteConnectionError(
                "OpenSSH authentication or host verification failed: " +
                (result.stderr.strip()[:350] or "Check SSH config, fingerprint and login method")
            )

    def _has_configured_master(self):
        result = subprocess.run(
            self._base_argv() + ["-O", "check"] + self._target_args(),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=self.timeout, check=False,
        )
        return result.returncode == 0

    def connect(self):
        if self._sftp is not None:
            return self
        if os.name != "posix" or not self._ssh:
            raise RemoteConnectionError("OpenSSH transport requires a local ssh executable on Linux/WSL/macOS")
        try:
            import paramiko  # only the SFTP packet codec, not Paramiko's SSH login
        except ImportError as exc:
            raise RemoteConnectionError("SFTP protocol adapter requires paramiko; install ppigfinder[recommended]") from exc
        try:
            if self._password is not None or not self._has_configured_master():
                self._start_master()
            # Request the SFTP *subsystem*, not a remote shell command.
            subsystem_argv = (self._base_argv() + ["-o", "ControlMaster=no", "-o", "BatchMode=yes",
                                                   "-s"] + self._target_args() + ["sftp"])
            self._subsystem = subprocess.Popen(subsystem_argv, stdin=subprocess.PIPE,
                                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self._pipe = _OpenSSHSubprocessChannel(self._subsystem)
            sftp = paramiko.SFTPClient(self._pipe)
            remote_home = sftp.normalize(".")
            if not remote_home.startswith("/"):
                raise RemoteConnectionError("SFTP did not report an absolute remote home directory")
            self._sftp = sftp
            self._home = remote_home
            self._root = remote_home.rstrip("/") + "/" + self.profile.remote_subdir
            return self
        except Exception:
            self.close()
            raise

    def test(self):
        result = super().test()
        result["transport"] = "openssh"
        return result

    def close(self):
        # Close the SFTP protocol before tearing down the multiplexed master.
        if self._sftp is not None:
            try:
                self._sftp.close()
            except (OSError, EOFError):
                pass
        self._sftp = None
        if self._pipe is not None:
            self._pipe.close()
        self._pipe = self._subsystem = None
        if self._socket_path and self._ssh and self._temp:
            try:
                subprocess.run(self._base_argv() + ["-O", "exit"] + self._target_args(),
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=5, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if self._temp is not None:
            self._temp.cleanup()
        self._temp = self._socket_path = self._home = self._root = None
        self._password = None
        self._client = None
