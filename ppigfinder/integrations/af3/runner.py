"""Build and (on explicit request) launch official AF3, Docker or an AF3 wrapper.

No upstream inference implementation or model weights are bundled. Inputs use
native alphafold3 JSON, not the AlphaFold Server list dialect. Never silently
submit to a scheduler: remote queues use a separate optional execution adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys

from .schema import load_native_json


@dataclass(frozen=True)
class AF3RunnerConfig:
    mode: str = "wrapper"  # official, docker, wrapper
    model_dir: str = ""
    db_dir: str = ""
    script: str = ""  # path to upstream run_alphafold.py (official)
    python: str = ""  # interpreter in the separately installed AF3 environment
    docker_image: str = "alphafold3"
    docker_command: str = "docker"
    wrapper_command: str = "af3"


def _binary(value: str) -> str | None:
    if not value.strip():
        return None
    return shutil.which(value) or (str(Path(value).expanduser().resolve()) if Path(value).expanduser().is_file() else None)


def _dir(path: str, name: str) -> Path:
    if not path.strip():
        raise ValueError(f"{name} is required; configure it outside the repository")
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        raise ValueError(f"{name} does not exist: {p}")
    return p


def build_af3_command(config: AF3RunnerConfig, input_json: str | Path, output_dir: str | Path) -> list[str]:
    """Dry-run preflight and produce shell-free argv; no side effects."""
    input_path = Path(input_json).expanduser().resolve()
    job = load_native_json(input_path)
    out = Path(output_dir).expanduser().resolve()
    if not str(output_dir).strip():
        raise ValueError("Output directory is required")
    if out == input_path or out == input_path.parent:
        raise ValueError("Use a dedicated output directory separate from the input JSON")
    if out.exists() and not out.is_dir():
        raise ValueError(f"Output path is not a directory: {out}")

    if config.mode == "official":
        script = Path(config.script).expanduser().resolve()
        if not config.script or not script.is_file():
            raise ValueError("Official AF3 script path must point to run_alphafold.py")
        if script.name != "run_alphafold.py":
            raise ValueError("Expected the official script named run_alphafold.py")
        python_exe = _binary(config.python or sys.executable)
        if not python_exe:
            raise ValueError("Python interpreter for AF3 not found")
        model_dir = _dir(config.model_dir, "AF3 model directory")
        db_dir = _dir(config.db_dir, "AF3 database directory")
        return [python_exe, str(script), f"--json_path={input_path}",
                f"--model_dir={model_dir}", f"--db_dir={db_dir}", f"--output_dir={out}"]

    if config.mode == "docker":
        docker_exe = _binary(config.docker_command)
        if not docker_exe:
            raise ValueError("Docker CLI is not available")
        model_dir = _dir(config.model_dir, "AF3 model directory")
        db_dir = _dir(config.db_dir, "AF3 database directory")
        if not config.docker_image or config.docker_image.startswith("-"):
            raise ValueError("Docker image name must be provided")
        return [docker_exe, "run", "--rm", "--gpus", "all",
                "--mount", f"type=bind,src={input_path.parent},dst=/ppig_input,readonly",
                "--mount", f"type=bind,src={out},dst=/ppig_output",
                "--mount", f"type=bind,src={model_dir},dst=/ppig_models,readonly",
                "--mount", f"type=bind,src={db_dir},dst=/ppig_databases,readonly",
                config.docker_image, "python", "run_alphafold.py",
                f"--json_path=/ppig_input/{input_path.name}",
                "--model_dir=/ppig_models", "--db_dir=/ppig_databases",
                "--output_dir=/ppig_output"]

    if config.mode == "wrapper":
        cmd = _binary(config.wrapper_command)
        if not cmd:
            raise ValueError("AF3 wrapper is not available; configure wrapper_command or use manual Server export")
        return [cmd, "--json-path", str(input_path), "--job-name", job["name"],
                "--workdir", str(out), "--stage", "all", "--executor", "local"]

    raise ValueError(f"Unknown AF3 runner mode: {config.mode!r}")


def run_af3(config: AF3RunnerConfig, input_json: str | Path, output_dir: str | Path, *, execute: bool = False) -> list[str] | subprocess.CompletedProcess:
    """Default is preview; explicit execute=True runs one local/container process."""
    argv = build_af3_command(config, input_json, output_dir)
    if not execute:
        return argv
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    # No shell, no arbitrary module commands, no nested scheduler submission.
    return subprocess.run(argv, check=True)
