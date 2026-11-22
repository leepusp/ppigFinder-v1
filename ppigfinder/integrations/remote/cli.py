"""ppigfinder-remote: profile management and explicit SSH/SFTP operations."""
from __future__ import annotations

import argparse
import getpass
import json
import sys

from .profiles import ProfileStore, RemoteProfile
from .transport import SSHTransport, preview_af3_wrapper
from .openssh import OpenSSHTransport


def parser_for_cli():
    parser = argparse.ArgumentParser(description="Optional ppigfinder SSH/SFTP connector (no job submission)")
    sub = parser.add_subparsers(dest="operation", required=True)
    p = sub.add_parser("add", help="Save non-secret connection settings")
    for flag in ("name", "host"):
        p.add_argument("--" + flag, required=True)
    p.add_argument("--user", default="", help="Optional username, defaults to SSH config")
    p.add_argument("--port", type=int, default=0, help="0 uses SSH config or port 22")
    p.add_argument("--remote-subdir", default="ppigfinder-runs")
    p.add_argument("--af3-wrapper", default="af3")
    sub.add_parser("list", help="List names and connection settings, never credentials")
    remove = sub.add_parser("remove")
    remove.add_argument("name")
    for command in ("test", "upload", "download"):
        current = sub.add_parser(command)
        current.add_argument("name")
        current.add_argument("--ask-password", action="store_true", help="Prompt once; no password is saved")
        current.add_argument("--transport", choices=("openssh", "paramiko"),
                             help="Defaults to OpenSSH where supported, otherwise Paramiko")
        if command == "upload":
            current.add_argument("--json", required=True, help="Validated native AF3 JSON to upload")
        if command == "download":
            current.add_argument("--remote-relative", required=True, help="Path inside remote project root")
            current.add_argument("--out", required=True)
    return parser


def main(argv=None):
    parser = parser_for_cli()
    args = parser.parse_args(argv)
    store = ProfileStore()
    try:
        if args.operation == "add":
            profile = RemoteProfile(args.name, args.host, args.user, args.port, args.remote_subdir, args.af3_wrapper)
            store.save(profile)
            print(f"REMOTE_PROFILE_SAVED={profile.name} (no secrets stored)")
        elif args.operation == "list":
            print(json.dumps([p.__dict__ for p in store.list()], indent=2))
        elif args.operation == "remove":
            store.delete(args.name)
            print(f"REMOTE_PROFILE_REMOVED={args.name}")
        else:
            profile = store.get(args.name)
            password = getpass.getpass("SSH password (not saved): ") if args.ask_password else None
            if args.operation == "upload":
                from ppigfinder.integrations.af3.schema import load_native_json
                job = load_native_json(args.json)
            use_openssh = args.transport == "openssh" or (
                args.transport is None and OpenSSHTransport.is_available()
            )
            backend = OpenSSHTransport if use_openssh else SSHTransport
            with backend(profile, password=password) as transport:
                if args.operation == "test":
                    print(json.dumps(transport.test(), indent=2))
                elif args.operation == "upload":
                    receipt = transport.upload_file(args.json)
                    print("REMOTE_AF3_UPLOAD=PASS")
                    print(json.dumps(receipt.as_dict(), indent=2))
                    print("AF3_PREVIEW_ONLY: Requires a site-approved compute allocation; do NOT run on a login node")
                    print(preview_af3_wrapper(profile, receipt, job["name"]))
                else:
                    print(json.dumps(transport.download_file(args.remote_relative, args.out), indent=2))
        return 0
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        print(f"REMOTE_ERROR={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
