# Remote transport v1: explicit contracts and security boundaries

The optional `ppigfinder.integrations.remote` package has three independent
layers: `profiles.py` (stdlib-only, non-secret persistence), `transport.py`
(Paramiko SSH/SFTP only when requested), `cli.py` (manual commands). GUI action
is in `ppigfinder.ui.remote_connections_dialog`, with blocking operations run
in a worker thread.

## Operations supported

| API | Side effects |
| --- | --- |
| `ProfileStore.list/get/save/delete` | Local JSON config only |
| `SSHTransport.connect/test` | SSH host-key check, authenticate, open SFTP; no remote process |
| `SSHTransport.upload_file` | Create private project folder, write file, verify remote SHA-256 |
| `SSHTransport.download_file` | Download one restricted relative path; verify checksum |
| `preview_af3_wrapper` | Build text preview only; no subprocess or scheduler |

**Do not use this module to execute AF3 on a login node.** Scheduler and
inference capabilities are distinct optional layers. Current remote execution
is intentionally **not implemented**.

## Threat model, limits and tests

- `RejectPolicy`: unknown or changed SSH host keys fail closed. Never use
  `AutoAddPolicy` or disable key verification.
- No saved secrets; profiles have a strict allow-list of six fields.
- Private remote subdirectory is relative to the remote SFTP home; `..`, shell
  metacharacters, absolute paths and symlinked project components are refused.
- Uploads are content-addressed and capped at 64 MiB in this first version.
- Checksums use streamed SHA-256 over local and remote SFTP content. SHA does
  not imply provenance/biological validity of the model.
- Atomic local download refuses overwriting existing results.
- Paramiko is imported lazily, so core ppigFinder and offline tests do not
  require a cluster, network or Paramiko.
- Tests use an isolated fake SFTP filesystem. Cross-platform production
  readiness requires a real-remote round trip, with actual authentication.

The current adapter supports direct SSH or straightforward `~/.ssh/config`
Host entries. ProxyJump, MFA keyboard-interactive, persistent background jobs,
remote shell execution and scheduler adapters remain intentionally separate.
