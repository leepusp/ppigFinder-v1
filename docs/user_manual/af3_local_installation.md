# AlphaFold 3: installation, preparation and optional execution

## Overview

ppigFinder **contains its own first-party AF3 integration**: protein FASTA to native JSON, schema preflight, a local/container execution adapter and a GUI launcher. It **does not bundle** the upstream AlphaFold 3 inference engine, model parameters or databases. Genome inspection, annotation, PPI design, exports and result interpretation work without a GPU or HPC.

There are **three independent paths**:

| Path | Requirements | Actual execution |
| --- | --- | --- |
| **AlphaFold Server** | Browser and account, subject to current server rules | Export `alphafoldserver` JSON and upload manually |
| **AF3 official** | Separately installed upstream `run_alphafold.py`, AF3 Python environment, databases, model weights and supported compute | Local native inference |
| **AF3 Docker** | Official image built from upstream source, Docker GPU support, databases and model weights | Containerized native inference |
| **AF3 wrapper** | Pre-existing compatible `af3` executable, e.g. an institutional wrapper | Local wrapper execution only; scheduler handling is separate |

> **AlphaFold Server JSON is not native AF3 JSON.** The Server dialect is a top-level list of jobs; the native `alphafold3` dialect contains one object per input file. Do not interchange them accidentally.

The official upstream guides are authoritative for requirements and licensing:

- [AlphaFold 3 repository](https://github.com/google-deepmind/alphafold3)
- [Installation and Docker setup](https://github.com/google-deepmind/alphafold3/blob/main/docs/installation.md)
- [Native input JSON format](https://github.com/google-deepmind/alphafold3/blob/main/docs/input.md)
- [Model parameter terms](https://github.com/google-deepmind/alphafold3/blob/main/WEIGHTS_TERMS_OF_USE.md)

## 1. Install ppigFinder first (AF3 not required)

### Linux / macOS

```bash
git clone https://github.com/leepusp/ppigFinder-v1.git
cd ppigFinder-v1
bash scripts/install_ppigfinder.sh
.venv/bin/python main.py
```

Requires Python 3.11 or newer. To select a specific interpreter, set `PPIG_PYTHON=/path/to/python3.11` before invoking the installer. On headless HPC nodes, use a supported graphical desktop session for the GUI. Installing ppigFinder does **not** install AF3 models or databases.

### Windows PowerShell

```powershell
git clone https://github.com/leepusp/ppigFinder-v1.git
cd ppigFinder-v1
powershell -ExecutionPolicy Bypass -File .\scripts\install_ppigfinder.ps1
.\.venv\Scripts\python.exe main.py
```

For Windows native inferencing, confirm upstream AF3 GPU/runtime support. Docker/WSL or a compatible remote environment may be required; the ppigFinder GUI itself is cross-platform but AF3 GPU inference is not guaranteed on every OS.

## 2. Generate AF3 input from a protein FASTA

For a pair of proteins, create `pairs.faa`:

```fasta
>bait
MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ
>prey
MKWVTFISLLFLFSSAYS
```

Use the **same Python interpreter** that runs ppigFinder:

```bash
.venv/bin/python -m ppigfinder.integrations.af3.cli prepare \
  --fasta pairs.faa --name bait_prey --seeds 1,2 \
  --out af3_native.json
.venv/bin/python -m ppigfinder.integrations.af3.cli validate --json af3_native.json
```

After installation, the equivalent command is `ppigfinder-af3 prepare ...`. Protein input validation deliberately rejects ambiguous characters and stop codons. RNA, DNA, ligands, PTMs, templates and external MSA are **not yet supported by this ppigFinder FASTA helper**. They can be authored using the [upstream official JSON specification](https://github.com/google-deepmind/alphafold3/blob/main/docs/input.md), but require a corresponding validated adapter before executing through this tool.

## 3. Preview and run with a pre-existing wrapper (DaVinci example)

The local wrapper mode is not a Slurm submission. Do not run GPU inference on an HPC login node; use an allocated compute session or the institution's approved scheduler interface.

```bash
.venv/bin/python -m ppigfinder.integrations.af3.cli doctor --mode wrapper
.venv/bin/python -m ppigfinder.integrations.af3.cli run \
  --mode wrapper --wrapper af3 \
  --json af3_native.json --output-dir ./af3_results
```

The `run` command only previews by default. After validating your allocation/GPU and wrapper compatibility, adding `--execute` will actually invoke the wrapper. **No scheduler job is submitted automatically.** The wrapper is institutional software and its exact `--json-path` contract should be checked against `af3 --help` on that host.

## 4. Official upstream AF3 installation

Follow [the official upstream installation guide](https://github.com/google-deepmind/alphafold3/blob/main/docs/installation.md) to obtain source code, dependencies, model parameters and genetic databases. Keep all of them **outside the ppigFinder Git directory**. Validate the installed `run_alphafold.py` with the official example before enabling the ppigFinder adapter.

### Official code and Docker image (separate from ppigFinder)

On a workstation with suitable access and adequate storage, the upstream sequence is:

```bash
mkdir -p "$HOME/apps"
git clone https://github.com/google-deepmind/alphafold3.git "$HOME/apps/alphafold3"
cd "$HOME/apps/alphafold3"
docker build -t alphafold3 -f docker/Dockerfile .
```

Before executing the container, obtain the **model weights under their upstream terms**
from [Google DeepMind](https://github.com/google-deepmind/alphafold3#obtaining-model-parameters)
and set up databases using the official instructions. For users who have adequate
available storage, the upstream database helper is:

```bash
cd "$HOME/apps/alphafold3"
# Downloads hundreds of GB; run only if this large transfer is intentional.
./fetch_databases.sh /path/to/af3_public_databases
```

The official guide currently describes approximately **252 GB compressed** and
**630 GB extracted** databases. These numbers can change; check before downloading.
If another administrator already provides weights/databases, reuse the existing
readable paths rather than downloading duplicates.

### Official Python environment and script

The upstream project may require a Python runtime different from ppigFinder's
Python 3.11 environment. Configure `--python` to point to the **separate AF3
runtime**. Follow official installation steps for that environment. The AF3
script is not pip-installed into ppigFinder.

Run a preview first (replace paths with the actual installation):

```bash
.venv/bin/python -m ppigfinder.integrations.af3.cli run \
  --mode official \
  --python /path/to/af3-env/bin/python \
  --script /path/to/alphafold3/run_alphafold.py \
  --model-dir /path/to/af3_models \
  --db-dir /path/to/af3_public_databases \
  --json af3_native.json --output-dir ./af3_results
```

Once the official AF3 installation, GPU, memory, model terms and available databases are verified, repeat with `--execute`. The adapter uses official argument names: `--json_path`, `--model_dir`, `--db_dir`, `--output_dir` (underscores, not wrapper-style hyphens).

## 5. Docker installation

Build the upstream image according to [Google DeepMind's Docker instructions](https://github.com/google-deepmind/alphafold3/blob/main/docs/installation.md). **ppigFinder does not build images, configure GPUs or download model weights automatically.** For a prepared `alphafold3` image:

```bash
.venv/bin/python -m ppigfinder.integrations.af3.cli run \
  --mode docker --image alphafold3 \
  --model-dir /path/to/af3_models \
  --db-dir /path/to/af3_public_databases \
  --json af3_native.json --output-dir ./af3_results
```

Inspect the preview and re-run with `--execute`. The adapter mounts the JSON input, output, weights and databases separately, with models/databases read-only. Docker GPU support (`--gpus all`) must be configured by the user. The output directory is created only when actual execution is authorized.

## 6. Use the GUI

Open ppigFinder with Python 3.11+ and choose **AlphaFold → AF3 Local/Container Runner**. Choose a native JSON input, an output folder and a mode. Supply the paths of the optional installation, click **Check configuration / Preview**, then **Execute locally** if appropriate. Execution is asynchronous in Qt, but **closing the window during a run is prevented** to avoid interrupting the process accidentally.

The existing **System → Capabilities and Integrations** menu only detects dependencies; its *Detected* status does **not** mean the engine has successfully predicted a structure.

## 7. Import results and validate scientifically

Use the existing **AlphaFold → Import AF3 Results Folder** action. Confirm that output CIF, summary confidence JSON, PAE/ipTM values and input/chain mappings correspond to the expected protein pair and seeds. A zero process exit code does not validate a biological interaction.

## 8. Troubleshooting

- `TypeError: unsupported operand type(s) for |`: `python3` is too old. Use Python 3.11+ and reinstall in a clean venv.
- `AF3_ERROR: ... not configured`: supply actual model/database or executable paths, or use manual Server JSON export.
- `Docker CLI is not available`: install Docker and verify GPU runtime separately.
- `Native AlphaFold 3 JSON must be one object`: you supplied Server/list JSON to the native adapter; use native preparation or the separate Server workflow.
- Missing Pyrodigal/BLAST/HMMER: these are optional prerequisites, not required to export AF3 inputs. Use the backend status window to inspect your active environment.
- Output errors or GPU OOM: follow the upstream performance/installation documentation. Do not raise resource requests silently or automatically resubmit.

All local and container paths in this document are **examples**, not preconfigured paths. No SSH identities, tokens, weights or private datasets should be committed to Git.
