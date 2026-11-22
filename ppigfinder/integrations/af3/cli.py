"""First-party AF3 setup, FASTA->native JSON and safe execution CLI.

Usage: ppigfinder-af3 doctor | prepare | validate | run
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from .runner import AF3RunnerConfig, build_af3_command, run_af3
from .schema import load_native_json, read_protein_fasta, write_native_json


def _config(args: argparse.Namespace) -> AF3RunnerConfig:
    return AF3RunnerConfig(
        mode=args.mode,
        model_dir=args.model_dir or "",
        db_dir=args.db_dir or "",
        script=args.script or "",
        python=args.python or "",
        docker_image=args.image or "alphafold3",
        docker_command=args.docker or "docker",
        wrapper_command=args.wrapper or "af3",
    )


def _add_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=("wrapper", "official", "docker"), default="wrapper")
    parser.add_argument("--model-dir", default="", help="Official AF3 model weights directory (outside Git)")
    parser.add_argument("--db-dir", default="", help="Official AF3 databases directory (outside Git)")
    parser.add_argument("--script", default="", help="Path to upstream run_alphafold.py")
    parser.add_argument("--python", default="", help="AF3 environment's Python interpreter")
    parser.add_argument("--image", default="alphafold3", help="Previously built Docker image")
    parser.add_argument("--docker", default="docker", help="Docker CLI path or name")
    parser.add_argument("--wrapper", default="af3", help="Existing wrapper executable")


def parser_for_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ppigfinder native AlphaFold 3 integration")
    sub = p.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="Write native AF3 object from protein FASTA")
    prepare.add_argument("--fasta", required=True)
    prepare.add_argument("--out", required=True, help="Output .json file")
    prepare.add_argument("--name", required=True, help="Prediction name")
    prepare.add_argument("--seeds", default="1", help="Comma-separated integers, e.g. 1,2,3")

    check = sub.add_parser("validate", help="Validate protein-only native AF3 input")
    check.add_argument("--json", required=True)

    doctor = sub.add_parser("doctor", help="Preview prerequisites; never runs AF3")
    _add_config(doctor)
    doctor.add_argument("--json", help="Optional AF3 input JSON to validate with the chosen runner")
    doctor.add_argument("--output-dir", help="Output dir for optional command preview")

    run = sub.add_parser("run", help="Preview or execute one local AF3 prediction")
    _add_config(run)
    run.add_argument("--json", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--execute", action="store_true", help="Required for actual inference; default is preview")
    return p


def main(argv: list[str] | None = None) -> int:
    p = parser_for_cli()
    args = p.parse_args(argv)
    try:
        if args.command == "prepare":
            seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
            result = write_native_json(args.out, read_protein_fasta(args.fasta), args.name, seeds)
            print(f"AF3_NATIVE_JSON=PASS {result}")
        elif args.command == "validate":
            d = load_native_json(args.json)
            print(f"AF3_NATIVE_JSON=PASS name={d['name']} chains={len(d['sequences'])}")
        elif args.command == "doctor":
            config = _config(args)
            print(f"mode={config.mode}")
            if args.json or args.output_dir:
                if not args.json or not args.output_dir:
                    p.error("doctor requires both --json and --output-dir for an execution preflight")
                cmd = build_af3_command(config, args.json, args.output_dir)
                print("AF3_PREFLIGHT=PASS")
                print("command:", shlex.join(cmd))
            else:
                import shutil
                from pathlib import Path
                if config.mode == "wrapper":
                    cmd = shutil.which(config.wrapper_command)
                    print(f"wrapper={cmd or 'NOT CONFIGURED'}")
                    print("AF3_PREFLIGHT=PARTIAL (validate input and execute a small job separately)")
                elif config.mode == "official":
                    for key, value in (("script", config.script), ("model_dir", config.model_dir), ("db_dir", config.db_dir)):
                        print(f"{key}={value or 'NOT CONFIGURED'} exists={bool(value and Path(value).expanduser().exists())}")
                    print("AF3_PREFLIGHT=PARTIAL (no weights/GPU/inference test)")
                else:
                    print(f"docker={shutil.which(config.docker_command) or 'NOT CONFIGURED'}")
                    print(f"image={config.docker_image} (not inspected)")
                    print("AF3_PREFLIGHT=PARTIAL (no image/weights/GPU test)")
        else:
            config = _config(args)
            argv_prepared = build_af3_command(config, args.json, args.output_dir)
            print("AF3_PREFLIGHT=PASS")
            print("command:", shlex.join(argv_prepared))
            if args.execute:
                print("AF3_EXECUTE=STARTED", flush=True)
                run_af3(config, args.json, args.output_dir, execute=True)
                print("AF3_EXECUTE=PROCESS_EXIT_0 (review outputs and scientific QC)")
            else:
                print("AF3_PREVIEW_ONLY=PASS (add --execute to run)")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AF3_ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        # Avoid showing secrets: configuration holds only paths, not credentials.
        print(f"AF3_RUN_FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
