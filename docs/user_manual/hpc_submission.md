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

For local AF3 (official Python runner, Docker or institutional wrapper) see
[AF3 installation and local execution](af3_local_installation.md). These local
adapters require no scheduler, remote connection or SSH.

## Generic Slurm process (advanced users)

1. Confirm the intended native AF3 schema and run-command syntax on the target cluster.
2. Generate AF3 JSONs, a job manifest, and scheduler scripts from ppigFinder.
3. Review `#SBATCH` directives for CPU, RAM, wall time, partition, GPU/GRES and array concurrency.
4. Activate the actual AF3 environment **inside** the allocation. Ensure that any wrapper's local executor does not submit nested Slurm jobs.
5. Submit with `sbatch` according to local cluster policy.
6. Inspect `squeue`, `sacct` and job logs with the correct account permissions; only after completion, transfer outputs for parsing.

Run these commands **on a host with Slurm configured**, after installing ppigFinder there:

```bash
ppigfinder-slurm validate path/to/reviewed_submit_af3.slurm
ppigfinder-slurm submit path/to/reviewed_submit_af3.slurm --confirm
ppigfinder-slurm status 12345
ppigfinder-slurm logs 12345
ppigfinder-slurm cancel 12345 --confirm
```

Replace `12345` with the returned job ID. Validation asks Slurm to check the script without enqueuing it. The logs command reports the stdout and stderr paths while Slurm retains the job details. The CLI uses the Slurm configuration of the host where it runs. The graphical SSH/SFTP dialog handles file transfers separately.

Set partition, GPU/GRES, account and other resources according to the target site's configuration. The generic script generator can also receive a user-defined `SlurmClusterProfile` with partition and GPU mappings.
