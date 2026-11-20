# Execution environments: from desktop to HPC

**HPC is optional.** ppigFinder's candidate discovery and JSON export are distinct from executing structure prediction. The application should not assume one cluster, SSH host, scheduler, GPU model or institutional account.

## Choose your route

| Route | Required access | Current path |
|---|---|---|
| **AlphaFold Server** | Web browser/account | Export JSON; submit manually; download/import outputs |
| **Local AF3 wrapper** | Installed runner, models, databases, appropriate resources | Command preparation via `AlphaFoldService`; end-to-end environment-specific validation required |
| **Slurm cluster** | Cluster account, installed AF3 and suitable allocation | Native job preparation and Slurm batch scripts; inspect all directives before submitting |
| **PBS / LSF** | Cluster-specific tools | Files for adapters exist; modular submission path is not established as complete |
| **Boltz-2 / FoldCP** | Validated independent installations | Input writer scaffolding available; runner integration remains provisional |

## Distinguish two independent settings

- **Prediction backend**: AlphaFold Server, native AF3, or a future validated alternative. Determines input schema and resulting file formats.
- **Execution target**: manual web submission, local process, or a scheduler/cluster. Determines job execution, monitoring, transfer and cancellation.

An institution-specific profile should contain values such as hostname, SSH port, remote workspace, scheduler type, queue/partition name, GPU request syntax, module commands, executable locations, database roots and resource limits. None belongs in general-purpose source code as an irrevocable default.

## Generic Slurm process (advanced users)

1. Confirm the intended native AF3 schema and run-command syntax on the target cluster.
2. Generate AF3 JSONs, a job manifest, and scheduler scripts from ppigFinder.
3. Review `#SBATCH` directives for CPU, RAM, wall time, partition, GPU/GRES and array concurrency.
4. Activate the actual AF3 environment **inside** the allocation. Ensure that any wrapper's local executor does not submit nested Slurm jobs.
5. Submit with `sbatch` according to local cluster policy.
6. Inspect `squeue`, `sacct` and job logs with the correct account permissions; only after completion, transfer outputs for parsing.

Example of commands to run **on the cluster** (substitute your validated script name):

```bash
sbatch path/to/reviewed_submit_af3.slurm
squeue -u "$USER"
sacct -u "$USER" --starttime today --format JobID,JobName,State,Elapsed,ExitCode
```

Do not copy resource requests from DaVinci without checking the target cluster. The presence of `ppigfinder/hpc/ssh_client.py`, `job_monitor.py`, `hpc_service.py` and other files does **not** by itself prove a working automated UI connection: some are empty/placeholder modules in the imported version.

## DaVinci is an example, not a dependency

The existing DaVinci profile and AF3 wrapper dry-run were validated previously for input preparation. The documented dry-run did not execute a full model inference. Default GRES/shard values and the choice of module activation vs `af3` in `PATH` differ across implementations and require reconciliation before production use.

See [DaVinci example](davinci_hpc.md), [HPC portability](../developer/hpc_portability.md), and [implementation status](../developer/feature_status.md).

## Security and reproducibility

Use SSH keys or institutional authentication rather than storing passwords in repository files; do not commit tokens, private paths, or user datasets. Record runner versions, model/database versions where allowed, seeds, input hashes, resource requests, job IDs, failures and outputs. Do not execute downloaded job scripts without inspection.
