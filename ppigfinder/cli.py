"""Terminal options for the ppigfinder desktop launcher."""

import argparse
from importlib.metadata import version
from importlib.resources import files
import pydoc
import sys


def main():
    args = sys.argv[1:]
    if args and args[0] in {"-h", "--help", "--version", "--manual", "manual"}:
        parser = argparse.ArgumentParser(prog="ppigfinder", description="Launch the desktop application or read its terminal manual.")
        parser.add_argument("--version", action="version", version=f"ppigfinder {version('ppigfinder')}")
        parser.add_argument("--manual", action="store_true", help="Read the quick manual offline")
        parser.add_argument("command", choices=["manual"], nargs="?", help="Also opens the offline manual")
        if args[0] in {"-h", "--help"}:
            print(files("ppigfinder").joinpath("terminal_banner.txt").read_text(encoding="ascii"))
        parser.parse_args(args)
        pydoc.pager(files("ppigfinder").joinpath("terminal_manual.txt").read_text(encoding="utf-8"))
        return 0

    from ppigfinder.app import main as launch

    return launch()
