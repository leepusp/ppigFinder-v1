"""User-owned, non-secret SSH connection profiles (stdlib only).

Profiles are never stored in the Git repository. Passwords, API tokens and
private key material are not accepted by the profile schema.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import tempfile

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_HOST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,252}$")
_USER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,63}$")
_PART = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
_EXEC = re.compile(r"^(?:[A-Za-z0-9_.-]+|/[A-Za-z0-9_./-]+)$")
_FIELDS = frozenset({"name", "host", "username", "port", "remote_subdir", "af3_wrapper"})


def safe_relative_path(value: str) -> str:
    """Accept only paths inside the private, dedicated remote root."""
    if not isinstance(value, str) or not value or len(value) > 400:
        raise ValueError("Remote relative path is empty or too long")
    if "\\" in value or value.startswith("/") or "//" in value:
        raise ValueError("Expected a POSIX path relative to the user's home directory")
    parts = value.split("/")
    if not all(_PART.fullmatch(part) and part not in {".", ".."} for part in parts):
        raise ValueError("Unsafe remote path component; use letters, numbers, '.', '_' or '-'")
    return value


@dataclass(frozen=True)
class RemoteProfile:
    name: str
    host: str                 # SSH host alias or DNS hostname
    username: str = ""       # Blank uses ~/.ssh/config or OS account
    port: int = 0            # Zero uses ~/.ssh/config or default 22
    remote_subdir: str = "ppigfinder-runs"
    af3_wrapper: str = "af3"

    def __post_init__(self) -> None:
        if not _NAME.fullmatch(self.name):
            raise ValueError("Profile name must begin with a letter and contain only letters/numbers/._-")
        if not _HOST.fullmatch(self.host):
            raise ValueError("SSH host must be a host alias or DNS name without shell syntax")
        if self.username and not _USER.fullmatch(self.username):
            raise ValueError("Invalid SSH user name")
        if type(self.port) is not int or not 0 <= self.port <= 65535:
            raise ValueError("Port must be 0 (SSH config) or 1-65535")
        safe_relative_path(self.remote_subdir)
        if not _EXEC.fullmatch(self.af3_wrapper) or ".." in self.af3_wrapper.split("/"):
            raise ValueError("AF3 wrapper must be a simple executable or absolute POSIX path")

    @classmethod
    def from_dict(cls, obj: dict) -> "RemoteProfile":
        if not isinstance(obj, dict) or set(obj) - _FIELDS:
            raise ValueError("Unexpected profile keys; secrets are not supported")
        return cls(**obj)


def default_store_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", "")
    root = Path(base).expanduser() if base and Path(base).is_absolute() else Path.home() / ".config"
    return root / "ppigfinder" / "connections.json"


class ProfileStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path).expanduser() if path else default_store_path()

    def list(self) -> tuple[RemoteProfile, ...]:
        if not self.path.exists():
            return ()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("profiles"), list):
            raise ValueError("Unsupported ppigfinder connections format")
        profiles = tuple(RemoteProfile.from_dict(item) for item in data["profiles"])
        if len(set(p.name for p in profiles)) != len(profiles):
            raise ValueError("Duplicate remote profile names")
        return tuple(sorted(profiles, key=lambda p: p.name.lower()))

    def get(self, name: str) -> RemoteProfile:
        for profile in self.list():
            if profile.name == name:
                return profile
        raise KeyError(f"No remote profile named {name!r}")

    def save(self, profile: RemoteProfile) -> None:
        current = {p.name: p for p in self.list()}
        current[profile.name] = profile
        self._write(current.values())

    def delete(self, name: str) -> None:
        current = {p.name: p for p in self.list()}
        if name not in current:
            raise KeyError(name)
        del current[name]
        self._write(current.values())

    def _write(self, profiles) -> None:
        parent = self.path.parent
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == "posix":
            os.chmod(parent, 0o700)
        content = json.dumps({"version": 1, "profiles": [asdict(p) for p in sorted(profiles, key=lambda p: p.name)]},
                             indent=2, ensure_ascii=False) + "\n"
        fd, temp = tempfile.mkstemp(prefix=".connections.", dir=str(parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if os.name == "posix":
                os.chmod(temp, 0o600)
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
