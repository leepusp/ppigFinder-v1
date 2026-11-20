"""Offline tests for OpenSSH authentication + Paramiko SFTP subsystem codec."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from ppigfinder.integrations.remote.profiles import RemoteProfile
from ppigfinder.integrations.remote.openssh import (
    OpenSSHTransport, _PasswordAskpass, _OpenSSHSubprocessChannel,
)
from test_remote_connections import FakeSFTP


class StubProcess:
    def __init__(self):
        self.stdin = None
        self.stdout = None
        self.closed = False

    def poll(self):
        return 0


class OpenSSHTests(unittest.TestCase):
    def test_reuses_configured_master_and_leaves_it_running(self):
        profile = RemoteProfile("cluster", "cluster", "testuser", port=2200)
        sftp = types.SimpleNamespace(normalize=lambda path: "/home/testuser", close=lambda: None)
        fake_codec = types.SimpleNamespace(SFTPClient=lambda stream: sftp)
        module = "ppigfinder.integrations.remote.openssh"
        with patch(f"{module}.os", wraps=os) as platform, \
             patch(f"{module}.shutil.which", return_value="/usr/bin/ssh"), \
             patch(f"{module}.subprocess.run", return_value=types.SimpleNamespace(returncode=0)) as run, \
             patch(f"{module}.subprocess.Popen", return_value=StubProcess()) as popen, \
             patch(f"{module}._OpenSSHSubprocessChannel"), \
             patch.dict(sys.modules, {"paramiko": fake_codec}):
            platform.name = "posix"
            with OpenSSHTransport(profile) as conn:
                self.assertEqual(conn.test()["status"], "SSH_SFTP_CONNECTED")

            run.assert_called_once()
            self.assertEqual(run.call_args.args[0], [
                "/usr/bin/ssh", "-o", "StrictHostKeyChecking=yes",
                "-O", "check", "-l", "testuser", "-p", "2200", "cluster",
            ])
            self.assertEqual(popen.call_args.args[0], [
                "/usr/bin/ssh", "-o", "StrictHostKeyChecking=yes",
                "-o", "ControlMaster=no", "-o", "BatchMode=yes",
                "-s", "-l", "testuser", "-p", "2200", "cluster", "sftp",
            ])

    @unittest.skipUnless(os.name == "posix", "OpenSSH askpass uses Unix sockets")
    def test_password_bridged_via_owner_only_socket_no_secret_in_argv_or_helper(self):
        with tempfile.TemporaryDirectory(prefix="ppig-askpass-") as tmp:
            root = Path(tmp)
            root.chmod(0o700)
            with _PasswordAskpass(root, "one-time-secret") as ask:
                env = dict(os.environ)
                env.update(ask.environment())
                self.assertNotIn("one-time-secret", repr(env))
                self.assertNotIn("one-time-secret", ask.helper_path.read_text())
                self.assertEqual(stat.S_IMODE(ask.helper_path.stat().st_mode), 0o700)
                result = subprocess.run([str(ask.helper_path)], capture_output=True,
                                        env=env, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "one-time-secret\n")
            self.assertFalse(Path(ask.socket_path).exists())
            self.assertFalse(ask.helper_path.exists())

    @unittest.skipUnless(os.name == "posix", "OpenSSH multiplexing requires POSIX")
    def test_ssh_auth_master_and_subsystem_use_config_and_no_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            def mock_run(argv, **kwargs):
                calls.append((argv, kwargs))
                return types.SimpleNamespace(returncode=0, stderr="", stdout="")
            sftp = FakeSFTP(Path(tmp) / "server")
            sftp.normalize = lambda path: "/home/testuser"
            created = []
            fake_codec = types.SimpleNamespace(SFTPClient=lambda stream: (created.append(stream) or sftp))
            profile = RemoteProfile("research-hpc", "research-hpc", "testuser", remote_subdir="ppigfinder-runs")
            with patch("ppigfinder.integrations.remote.openssh.shutil.which", return_value="/usr/bin/ssh"), \
                 patch("ppigfinder.integrations.remote.openssh.subprocess.run", side_effect=mock_run), \
                 patch("ppigfinder.integrations.remote.openssh.subprocess.Popen", return_value=StubProcess()) as popen, \
                 patch("ppigfinder.integrations.remote.openssh._OpenSSHSubprocessChannel") as codec, \
                 patch.dict(sys.modules, {"paramiko": fake_codec}):
                conn = OpenSSHTransport(profile, password="NOT_STORED")
                conn.connect()
                self.assertEqual(conn.test()["status"], "SSH_SFTP_CONNECTED")
                self.assertEqual(conn.test()["transport"], "openssh")
                self.assertEqual(conn._password, None)
                self.assertEqual(len(calls), 1)
                auth_argv = calls[0][0]
                self.assertIn("StrictHostKeyChecking=yes", auth_argv)
                self.assertIn("PubkeyAuthentication=no", auth_argv)
                self.assertIn("PreferredAuthentications=password,keyboard-interactive", auth_argv)
                self.assertIn("-M", auth_argv)
                self.assertNotIn("NOT_STORED", repr(calls))
                subsystem_argv = popen.call_args.args[0]
                self.assertIn("-s", subsystem_argv)
                self.assertEqual(subsystem_argv[-1], "sftp")
                self.assertIn("ControlMaster=no", subsystem_argv)
                self.assertNotIn("NOT_STORED", repr(popen.call_args))
                self.assertEqual(len(created), 1)
                src = Path(tmp)/"input.json"
                src.write_bytes(b'{"test":true}')
                receipt = conn.upload_file(src)
                self.assertEqual(receipt.sha256, hashlib.sha256(src.read_bytes()).hexdigest())
                self.assertEqual(conn.upload_file(src), receipt)
                out = Path(tmp)/"download.json"
                relative = receipt.remote_path.removeprefix(conn.remote_root + "/")
                self.assertEqual(conn.download_file(relative, out)["sha256"], receipt.sha256)
                self.assertEqual(out.read_bytes(), src.read_bytes())
                conn.close()
                self.assertEqual(len(calls), 2)
                self.assertIn("exit", calls[1][0])

    @unittest.skipUnless(os.name == "posix", "select() on pipes requires POSIX")
    def test_ssh_channel_is_duplex_binary_stream(self):
        # Fake Popen with a pair of pipes: verify direct SFTP packet framing IO.
        read_remote, write_local = os.pipe()
        read_local, write_remote = os.pipe()
        p = StubProcess()
        p.stdin = os.fdopen(write_local, "wb", buffering=0)
        p.stdout = os.fdopen(read_local, "rb", buffering=0)
        pipe = _OpenSSHSubprocessChannel(p, timeout=1)
        try:
            self.assertEqual(pipe.get_name(), "ppigfinder-openssh-sftp")
            self.assertEqual(pipe.send(b"hello"), 5)
            self.assertEqual(os.read(read_remote, 5), b"hello")
            os.write(write_remote, b"reply")
            self.assertEqual(pipe.recv(5), b"reply")
        finally:
            pipe.close()
            os.close(read_remote)
            os.close(write_remote)


if __name__ == "__main__":
    unittest.main()
