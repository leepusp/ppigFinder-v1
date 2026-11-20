# Optional integrations and capability detection

ppigFinder is designed to operate without HPC, SSH, a scheduler, a GPU or a
running AlphaFold installation. **Prediction input preparation is separate from
execution.** The optional capability registry documents the current surface; it
does not silently install a tool or attempt network connections.

## Inspect without a GUI

```bash
python -m ppigfinder.infrastructure.capabilities
python -m ppigfinder.infrastructure.capabilities --json
```

The existing **System / Capabilities and Integrations** window uses the same
registry. It does not call external executables or access network services.

## Meaning of states

| State | Meaning |
|---|---|
| `available` | A ppigFinder code path exists for the listed operation, not a scientific validation guarantee |
| `detected` | An optional executable/module is locally discoverable; inference or tool execution was not tested |
| `not_configured` | An optional prerequisite or explicit site profile is absent |
| `not_implemented` | The advertised adapter does not yet exist in the modular implementation |

The **AlphaFold Server** integration is currently **manual JSON export**. A
usable website, account, or automated API submission is not guaranteed.

The **AF3 local wrapper** is only *detected* by executable presence; model
weights, databases, GPU compatibility and a successful inference have not been
verified. Likewise, Slurm script export requires an explicit validated profile.
A scheduler script is **not** a remote transport or job manager.

Boltz-2 and FoldCP currently support **input generation**. Their execution
adapters are intentionally marked **not implemented**.

## Adding an integration

1. Add an independent exporter/parser or execution adapter with a narrow API.
2. Add one capability descriptor, stating exactly which operations exist.
3. Detect only inexpensive, side-effect-free prerequisites at application startup.
4. Add deterministic tests for missing and present dependencies.
5. Mark a remote or local runner as supported only after an end-to-end run is validated.

Do not put site-specific Slurm directives, SSH identities or user secrets into
scientific domain code or committed repository defaults.
