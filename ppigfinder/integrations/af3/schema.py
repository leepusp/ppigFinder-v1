"""Native AlphaFold 3 protein JSON construction/validation (stdlib only).

Unlike the AlphaFold Server dialect, a native AF3 input is one JSON *object*.
Current helpers intentionally support proteins only. Other molecule types
require explicit format adapters rather than silent conversion.
"""
from __future__ import annotations

import json
import re
import string
from pathlib import Path

_STANDARD_AA = frozenset("ACDEFGHIKLMNPQRSTVWY")


def read_protein_fasta(path: str | Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    label: str | None = None
    chunks: list[str] = []
    with Path(path).open(encoding="utf-8") as stream:
        for number, raw in enumerate(stream, 1):
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if label is not None:
                    records.append((label, "".join(chunks)))
                label = line[1:].strip().split(maxsplit=1)[0]
                if not label:
                    raise ValueError(f"FASTA record at line {number} has no identifier")
                chunks = []
            elif label is None:
                raise ValueError(f"FASTA sequence precedes header at line {number}")
            else:
                chunks.append("".join(line.split()).upper())
    if label is not None:
        records.append((label, "".join(chunks)))
    if not records:
        raise ValueError("FASTA is empty")
    if len(records) > 26:
        raise ValueError("This minimal protein writer supports at most 26 chains")
    for _, seq in records:
        _check_protein(seq)
    return records


def _check_protein(seq: str) -> None:
    if not seq:
        raise ValueError("Protein sequence cannot be empty")
    bad = sorted(set(seq.upper()) - _STANDARD_AA)
    if bad:
        raise ValueError(
            f"Unsupported protein residue(s) {','.join(bad)}. "
            "Resolve ambiguous/noncanonical residues before export."
        )


def prepare_native_job(records: list[tuple[str, str]], name: str, seeds: list[int]) -> dict:
    if not records or len(records) > 26:
        raise ValueError("Expected 1 to 26 protein chains")
    clean_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", name).strip("._-")[:100]
    if not clean_name:
        raise ValueError("Job name must not be empty")
    if not seeds or any(type(x) is not int or x < 0 for x in seeds):
        raise ValueError("modelSeeds must contain non-negative integers")
    sequences = []
    for i, (label, seq) in enumerate(records):
        sequence = "".join(seq.split()).upper()
        _check_protein(sequence)
        sequences.append({"protein": {"id": string.ascii_uppercase[i], "sequence": sequence}})
    return {"name": clean_name, "modelSeeds": seeds, "sequences": sequences,
            "dialect": "alphafold3", "version": 1}


def validate_native_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Native AlphaFold 3 JSON must be one object, not a list. Use Server export for arrays.")
    if payload.get("dialect") != "alphafold3":
        raise ValueError("Expected dialect='alphafold3' (not alphafoldserver)")
    if type(payload.get("version")) is not int or payload["version"] not in (1, 2, 3, 4):
        raise ValueError("Unsupported native AF3 input version")
    if not isinstance(payload.get("name"), str) or not payload["name"].strip():
        raise ValueError("AF3 job requires a name")
    seeds = payload.get("modelSeeds")
    if not isinstance(seeds, list) or not seeds or any(type(x) is not int or x < 0 for x in seeds):
        raise ValueError("AF3 modelSeeds must contain at least one non-negative integer")
    chains = payload.get("sequences")
    if not isinstance(chains, list) or not chains:
        raise ValueError("AF3 requires at least one sequence")
    ids: set[str] = set()
    for index, chain in enumerate(chains, start=1):
        if not isinstance(chain, dict) or len(chain) != 1 or "protein" not in chain:
            raise ValueError(f"Protein-only AF3 adapter: unsupported chain #{index}")
        protein = chain["protein"]
        if not isinstance(protein, dict):
            raise ValueError(f"Chain #{index} must be an object")
        chain_ids = protein.get("id")
        if isinstance(chain_ids, str):
            chain_ids = [chain_ids]
        if not isinstance(chain_ids, list) or not chain_ids or any(not isinstance(x, str) or not x for x in chain_ids):
            raise ValueError(f"Chain #{index} missing valid id")
        for chain_id in chain_ids:
            if chain_id in ids:
                raise ValueError(f"Duplicate chain identifier {chain_id!r}")
            ids.add(chain_id)
        if not isinstance(protein.get("sequence"), str):
            raise ValueError(f"Chain #{index} missing protein sequence")
        _check_protein(protein["sequence"])
    return payload


def load_native_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Input JSON does not exist: {p}")
    with p.open(encoding="utf-8") as stream:
        return validate_native_payload(json.load(stream))


def write_native_json(path: str | Path, records: list[tuple[str, str]], name: str, seeds: list[int]) -> Path:
    p = Path(path)
    payload = prepare_native_job(records, name, seeds)
    validate_native_payload(payload)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p
