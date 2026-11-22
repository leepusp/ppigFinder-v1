# Contributing to ppigfinder

Contributions are welcome. Use English in code, documentation, issues and pull requests where possible. For major workflow changes, describe the scientific use case and supported inputs/outputs before implementing them.

## Development setup

1. Install Python 3.11, clone the repository and create a virtual environment.
2. Install `python -m pip install -e ".[gui,recommended,dev]"`.
3. Run `python -m compileall -q ppigfinder` and the relevant developer checks in `scripts/developer/`.
4. Run the GUI in a graphical desktop session and confirm the changed workflow with a small, non-sensitive dataset.
5. Keep generic science logic separate from HPC, scheduler, institutional profile and interface adapters.

## Backend contributions

Do not hard-code a specific cluster, module location, user directory, GPU model or credential into scientific modules. A new prediction backend should declare its input schema, runner contract, output parser, metrics and compatibility constraints. An execution backend should independently handle environment checks, submission, monitoring, failure reporting and result retrieval.

## Documentation and screenshots

Use anonymized or public example data. **Label screenshots with the exact ppigfinder version**. Schematic SVGs and historical screenshots should not be passed off as current application screenshots.

## Review

Explain how you tested the change, known limitations, version compatibility, and whether user-facing commands/menus or JSON formats changed. See [SECURITY.md](SECURITY.md) for sensitive-data practices.
