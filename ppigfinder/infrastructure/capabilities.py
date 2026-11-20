"""Read-only, offline capability registry for optional ppigFinder integrations.

No network connection, scheduler submission, executable invocation or Qt import
occurs while discovering capabilities. Presence of an executable is NOT proof
that its computation backend has been validated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import argparse
import importlib.util
import json
import shutil
from typing import Callable


class CapabilityStatus(str, Enum):
    AVAILABLE = "available"           # Code path built into ppigFinder
    DETECTED = "detected"             # Dependency exists, operation not verified
    NOT_CONFIGURED = "not_configured" # Optional dependency/configuration absent
    NOT_IMPLEMENTED = "not_implemented" # No functional adapter exists yet


@dataclass(frozen=True)
class Capability:
    identifier: str
    label: str
    status: CapabilityStatus
    operations: tuple[str, ...]
    detail: str

    def as_dict(self) -> dict:
        return {
            "id": self.identifier,
            "label": self.label,
            "status": self.status.value,
            "operations": list(self.operations),
            "detail": self.detail,
        }


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def collect_capabilities(
    *,
    which: Callable[[str], str | None] | None = None,
    module_probe: Callable[[str], bool] | None = None,
) -> tuple[Capability, ...]:
    """Inspect local prerequisites without importing or executing optional tools.

    `which` and `module_probe` are injected for deterministic tests. No probes
    imply that a remote server, scheduler, model database or service works.
    """
    which = which if which is not None else shutil.which
    module_probe = module_probe if module_probe is not None else _has_module

    def executable(label: str, identifier: str, command: str, operation: str) -> Capability:
        detected = bool(which(command))
        return Capability(
            identifier, label,
            CapabilityStatus.DETECTED if detected else CapabilityStatus.NOT_CONFIGURED,
            (operation,),
            f"{command} found in PATH; execution not validated" if detected
            else f"Install/configure {command} to enable this optional feature",
        )

    def python_module(label: str, identifier: str, module: str, operation: str) -> Capability:
        detected = bool(module_probe(module))
        return Capability(
            identifier, label,
            CapabilityStatus.DETECTED if detected else CapabilityStatus.NOT_CONFIGURED,
            (operation,),
            f"Python module {module} detected; runtime not validated" if detected
            else f"Install the optional Python module {module}",
        )

    return (
        Capability("genome_io", "Genome and project files", CapabilityStatus.AVAILABLE,
                   ("import", "export"), "Built-in readers, writers and project helpers"),
        Capability("afserver_export", "AlphaFold Server", CapabilityStatus.AVAILABLE,
                   ("export_json", "manual_submission"),
                   "Creates AlphaFold Server JSON. Upload in browser manually; server availability not checked"),
        Capability("af3_input", "AlphaFold 3 inputs", CapabilityStatus.AVAILABLE,
                   ("export_json",), "Protein-only native AF3 input writer; inference is separate"),
        Capability("af3_results", "AlphaFold 3 result import", CapabilityStatus.AVAILABLE,
                   ("import_results", "summarize"), "Local result parser; format coverage depends on input files"),
        Capability("boltz2_input", "Boltz-2 input export", CapabilityStatus.AVAILABLE,
                   ("export_input",), "Input generation only; runner not implemented"),
        Capability("foldcp_input", "FoldCP input export", CapabilityStatus.AVAILABLE,
                   ("export_input",), "Input generation only; runner not implemented"),
        python_module("Pyrodigal", "pyrodigal", "pyrodigal", "predict_orfs"),
        executable("BLAST+", "blast", "blastp", "sequence_search"),
        executable("HMMER3", "hmmer", "hmmsearch", "profile_search"),
        executable("AlphaFold 3 local wrapper", "af3_local", "af3", "execute_local"),
        Capability("scheduler_script", "Scheduler script export", CapabilityStatus.NOT_CONFIGURED,
                   ("export_slurm_script",),
                   "Requires explicit site/cluster resource profile; not a remote scheduler connection"),
        Capability("ssh_transport", "Remote SSH/SFTP transport",
                   CapabilityStatus.DETECTED if module_probe("paramiko") else CapabilityStatus.NOT_CONFIGURED,
                   ("connect", "upload", "download"),
                   "SSH/SFTP adapter installed; configure a user profile and test the remote host"
                   if module_probe("paramiko") else "Install optional Paramiko to use remote SSH/SFTP"),
        Capability("remote_scheduler", "Remote job management", CapabilityStatus.NOT_IMPLEMENTED,
                   ("submit", "monitor", "cancel", "collect"),
                   "No verified pluggable Slurm/PBS/LSF lifecycle adapter"),
        Capability("boltz2_runner", "Boltz-2 execution", CapabilityStatus.NOT_IMPLEMENTED,
                   ("execute",), "Only input generation is available"),
        Capability("foldcp_runner", "FoldCP execution", CapabilityStatus.NOT_IMPLEMENTED,
                   ("execute",), "Only input generation is available"),
        Capability("afserver_automation", "AlphaFold Server automation", CapabilityStatus.NOT_IMPLEMENTED,
                   ("submit_online", "retrieve_online"),
                   "Use manual browser submission; no supported web API integration is implemented"),
    )


def capabilities_as_dicts() -> list[dict]:
    return [cap.as_dict() for cap in collect_capabilities()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline ppigFinder capability report")
    parser.add_argument("--json", action="store_true", help="Machine-readable report")
    args = parser.parse_args(argv)
    capabilities = collect_capabilities()
    if args.json:
        print(json.dumps([cap.as_dict() for cap in capabilities], indent=2))
    else:
        for cap in capabilities:
            print(f"{cap.identifier:24} {cap.status.value:17} {cap.label}: {cap.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
