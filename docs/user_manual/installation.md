# Installation and first launch

ppigFinder is a Python desktop application, not a hosted web service. The **core genome-analysis workflow does not require HPC**, Slurm, AlphaFold weights or an internet connection after tools and data are installed. Some analysis features use optional external executables.

## Requirements

| Component | Purpose | Required for |
|---|---|---|
| Python **3.11** (recommended starting point) | Application runtime | Desktop and scientific Python modules |
| PyQt6 >= 6.4 | Graphical interface | Desktop mode |
| NumPy >= 1.21, Matplotlib >= 3.5 | Numerical work and plotting | Core package |
| Pyrodigal >= 2.0 | Gene calling | Recommended prokaryotic ORF mode |
| NCBI BLAST+ | Similarity search | BLAST-based annotation only |
| HMMER3 | Domain/profile search | External HMM searches only |
| Paramiko >= 2.9 | SSH/SFTP client library | Optional remote-compute use |
| AF3 installation, models, databases, GPU | Structural inference | Only when running AF3 locally or remotely |

The current `pyproject.toml` requires Python `>=3.11`, aligned with the implementation described in the preprint. This documentation **recommends 3.11 until CI and fresh installations validate a broader matrix**. PyQt5 support may exist in legacy code, but the documented install below uses PyQt6.

## Recommended installers

From a source checkout, open the graphical setup assistant. On Windows,
double-click **scripts → Install ppigFinder.vbs** in File Explorer. This uses
a windowless Python launcher. You can also start the assistant from a terminal:

```powershell
# Windows
py -3.11 scripts/install_ppigfinder.py
```

```bash
# Linux and macOS
python3 scripts/install_ppigfinder.py
```

Choose an empty installation folder or an existing virtual environment, select
the optional Pyrodigal and SSH/SFTP dependencies, then select **Install**.
Select **Open ppigFinder** when the installation is complete. The default
destination is `.venv` in the checkout.

The graphical installer needs Tk and a graphical session. Add `--terminal`
to the command for a terminal-only installation or `--desktop-only` to omit
optional Python dependencies. An initial installation normally downloads
Python packages. BLAST+, HMMER and AlphaFold engines are installed separately.

The terminal installer prints the package name, the manual link and the path
to the installed launcher. Run `py -3.11 scripts/install_ppigfinder.py --terminal`
on Windows or `python3 scripts/install_ppigfinder.py --terminal` on Linux/macOS.

To reinstall only ppigFinder, run the installed environment's Python with
`-m pip uninstall ppigfinder`, then open the setup assistant again and select
the same environment. Projects and other Python packages remain in place.
For a fresh dependency check, choose a new empty environment instead.

For an editable development installation, use `bash scripts/install_ppigfinder.sh` on Linux/macOS or
`powershell -ExecutionPolicy Bypass -File .\scripts\install_ppigfinder.ps1`
on Windows. Both install the desktop in `.venv` without installing AF3 inference,
models, databases or any scheduler. Python 3.11+ is mandatory. See the
[complete AlphaFold 3 setup guide](af3_local_installation.md).

## Linux

```bash
git clone https://github.com/leepusp/ppigFinder-v1.git
cd ppigFinder-v1
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[gui,recommended]"
python main.py
```

You need a graphical session (`DISPLAY` or equivalent). On headless SSH login nodes, Qt may fail with messages about the `xcb` display plugin; run on a workstation or a supported graphical session rather than launching the GUI on a headless login node.

## Windows 10/11 PowerShell

Install Python 3.11 and Git first, then open PowerShell:

```powershell
git clone https://github.com/leepusp/ppigFinder-v1.git
cd ppigFinder-v1
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[gui,recommended]"
python main.py
```

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe` directly to run `-m pip` and `main.py`. BLAST+ and HMMER executables may require separate installations or a WSL environment; confirm how the selected backend is detected before using it.

## macOS

Install a Python 3.11 distribution compatible with your hardware. Use the Linux/macOS commands above in Terminal. Verify that PyQt6 imports successfully in your environment before proceeding.

## Quick diagnostic

```bash
python -c "import sys, numpy, matplotlib; from PyQt6 import QtWidgets; print(sys.version.split()[0], 'Qt OK')"
python -m pip show ppigfinder
```

Within the UI, inspect the backend status indicators. They represent **availability in your environment**, not universal requirements. If a tool is missing, first check the corresponding user-manual section.

## Installed launcher and execution modes

Open `.venv\Scripts\ppigfinder.exe` on Windows or run `.venv/bin/ppigfinder` on Linux/macOS. Use the corresponding path under your selected folder if you changed the destination.

- **Local desktop:** genome analysis, ORFs, annotations and AF3 JSON preparation.
- **Local structural prediction:** configure the official AF3, Docker or wrapper runner. See [local AF3 setup](af3_local_installation.md).
- **Optional HPC:** configure a host and use SSH/SFTP for transfers. On a Slurm host, `ppigfinder-slurm resources` lists configured resources and `validate` checks a batch script before submission. See [execution environments](hpc_submission.md) and [remote connections](remote_connections.md).

The source installer has been exercised on Windows. The terminal install is configured for Windows, Linux and macOS in CI.

## No HPC? You can still use the software

You can prepare ORFs, annotations, candidate pairs and **AlphaFold Server**-compatible JSON files on a regular computer. Submit supported jobs manually through the [AlphaFold Server](https://alphafoldserver.com/) web interface (subject to its current account policies) and import results after downloading them.

Proceed to the [complete guide](complete_guide.md) or [first tutorial](../tutorials/xanthomonas.md).
