"""Offline contract tests for the independent SSH/SFTP adapter."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch
import sys
import types

from ppigfinder.integrations.remote.profiles import ProfileStore, RemoteProfile, safe_relative_path
from ppigfinder.integrations.remote.transport import SSHTransport, preview_af3_wrapper


class FakeSFTP:
    def __init__(self, root: Path):
        self.root = root
        (root / "home" / "testuser").mkdir(parents=True, exist_ok=True)

    def mapped(self, remote: str) -> Path:
        if not remote.startswith("/home/testuser"):
            raise AssertionError("Attempted to access a path outside remote home")
        return self.root / remote.removeprefix("/")

    def lstat(self, path):
        return self.mapped(path).lstat()

    def mkdir(self, path, mode=0o700):
        self.mapped(path).mkdir(mode=mode)

    def open(self, path, mode="rb"):
        return self.mapped(path).open(mode)

    def put(self, src, dst, confirm=True):
        shutil.copyfile(src, self.mapped(dst))

    def get(self, src, dst):
        shutil.copyfile(self.mapped(src), dst)

    def rename(self, src, dst):
        self.mapped(src).rename(self.mapped(dst))

    def remove(self, path):
        self.mapped(path).unlink()

    def close(self):
        pass


class RemoteConnectorTests(unittest.TestCase):
    def test_profile_store_permissions_and_no_password_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProfileStore(Path(tmp) / "private" / "connections.json")
            p = RemoteProfile("research-hpc", "research-hpc", remote_subdir="ppigfinder-runs")
            store.save(p)
            self.assertEqual(store.get("research-hpc"), p)
            data = store.path.read_text()
            self.assertNotIn("password", data)
            self.assertEqual(json.loads(data)["version"], 1)
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(store.path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(store.path.parent.stat().st_mode), 0o700)
            store.delete("research-hpc")
            self.assertEqual(store.list(), ())

    def test_invalid_profiles_and_paths_rejected(self):
        invalid = ["../escape", "/outside", "a//b", "abc;rm", "a/./b", "a/../b", "a\\b", "", "a/ space"]
        for name in invalid:
            with self.subTest(path=name), self.assertRaises(ValueError):
                safe_relative_path(name)
        for obj in (
            {"name": "bad;cmd", "host": "research-hpc"},
            {"name": "test", "host": "user@host"},
            {"name": "test", "host": "remote", "remote_subdir": "../../"},
            {"name": "test", "host": "remote", "password": "SECRET"},
            {"name": "test", "host": "remote", "af3_wrapper": "af3;reboot"},
            {"name": "test", "host": "remote", "port": True},
        ):
            with self.subTest(profile=obj), self.assertRaises(ValueError):
                RemoteProfile.from_dict(obj)

    def test_upload_sha256_and_download_sha256_and_no_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            local = tmp / "af3.json"
            data = b'{"dialect":"alphafold3","name":"test"}'
            local.write_bytes(data)
            profile = RemoteProfile("site", "example.test", remote_subdir="ppigfinder-runs")
            transport = SSHTransport(profile)
            transport._sftp = FakeSFTP(tmp / "server")
            transport._home = "/home/testuser"
            transport._root = "/home/testuser/ppigfinder-runs"
            receipt = transport.upload_file(local)
            self.assertEqual(receipt.sha256, hashlib.sha256(data).hexdigest())
            self.assertIn("/inputs/", receipt.remote_path)
            self.assertEqual(receipt, transport.upload_file(local))  # same content is idempotent
            command = preview_af3_wrapper(profile, receipt, "test")
            self.assertIn("--executor local", command)
            self.assertNotIn("sbatch", command)
            out = tmp / "downloaded.json"
            relative = receipt.remote_path.removeprefix(transport.remote_root + "/")
            result = transport.download_file(relative, out)
            self.assertEqual(out.read_bytes(), data)
            self.assertEqual(result["sha256"], receipt.sha256)
            with self.assertRaises(FileExistsError):
                transport.download_file(relative, out)
            with self.assertRaises(ValueError):
                transport.download_file("../escape.json", tmp / "escape.json")
            # No call in this test executes a command via SSH; only fake SFTP methods exist.

    def test_symlink_directory_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            profile = RemoteProfile("site", "example.test")
            transport = SSHTransport(profile)
            fake = FakeSFTP(tmp / "server")
            transport._sftp = fake
            transport._home = "/home/testuser"
            transport._root = "/home/testuser/ppigfinder-runs"
            original_lstat = fake.lstat
            fake.lstat = lambda path: (
                types.SimpleNamespace(st_mode=stat.S_IFLNK)
                if path == transport._root else original_lstat(path)
            )
            f = tmp / "input.json"
            f.write_text("test")
            with self.assertRaises(ValueError):
                transport.upload_file(f)

    def test_host_key_policy_is_reject_and_never_auto_add(self):
        clients = []
        class StrictPolicy: pass
        class MockSSHClient:
            def __init__(self):
                self.loaded = False
                self.policy = None
                clients.append(self)
            def load_system_host_keys(self):
                self.loaded = True
            def set_missing_host_key_policy(self, policy):
                self.policy = policy
            def connect(self, **kwargs):
                self.kwargs = kwargs
            def open_sftp(self):
                return MockSftp()
            def close(self): pass
        class MockSftp:
            def normalize(self, path): return "/home/testuser"
            def close(self): pass
        fake = types.SimpleNamespace(SSHClient=MockSSHClient, RejectPolicy=StrictPolicy)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(Path, "home", return_value=Path(tmp)), \
             patch.dict(sys.modules, {"paramiko": fake}):
            with SSHTransport(RemoteProfile("site", "example.test"), password="in-memory-only") as session:
                self.assertTrue(session.test()["status"] == "SSH_SFTP_CONNECTED")
        self.assertTrue(clients[0].loaded)
        self.assertIsInstance(clients[0].policy, StrictPolicy)
        self.assertEqual(clients[0].kwargs["password"], "in-memory-only")
        self.assertIsNone(session._password)

    def test_explicit_password_does_not_use_private_keys_or_agent(self):
        calls = []
        class StrictPolicy: pass
        class MockSftp:
            def normalize(self, path): return "/home/testuser"
            def close(self): pass
        class MockSSHClient:
            def load_system_host_keys(self): pass
            def set_missing_host_key_policy(self, policy):
                self.policy = policy
            def connect(self, **kwargs):
                calls.append(kwargs)
            def open_sftp(self): return MockSftp()
            def close(self): pass
        fake = types.SimpleNamespace(SSHClient=MockSSHClient, RejectPolicy=StrictPolicy)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(Path, "home", return_value=Path(tmp)), \
             patch.dict(sys.modules, {"paramiko": fake}):
            with SSHTransport(RemoteProfile("research-hpc", "example.test"), password="test-secret") as conn:
                self.assertEqual(conn.test()["status"], "SSH_SFTP_CONNECTED")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["password"], "test-secret")
        self.assertIsNone(calls[0]["key_filename"])
        self.assertFalse(calls[0]["allow_agent"])
        self.assertFalse(calls[0]["look_for_keys"])

    def test_remote_checksum_failure_cleans_partial_upload(self):
        class CorruptSFTP(FakeSFTP):
            def put(self, src, dst, confirm=True):
                self.mapped(dst).write_bytes(b"corrupted")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            file = tmp / "sample.json"
            file.write_bytes(b"valid bytes")
            transport = SSHTransport(RemoteProfile("site", "example.test"))
            transport._sftp = CorruptSFTP(tmp / "server")
            transport._home = "/home/testuser"
            transport._root = "/home/testuser/ppigfinder-runs"
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                transport.upload_file(file)
            remote_inputs = tmp / "server/home/testuser/ppigfinder-runs/inputs"
            self.assertFalse(list(remote_inputs.iterdir()))

    def test_missing_paramiko_does_not_block_profile_io(self):
        self.assertEqual(RemoteProfile("local", "test.example").name, "local")


if __name__ == "__main__":
    unittest.main()
