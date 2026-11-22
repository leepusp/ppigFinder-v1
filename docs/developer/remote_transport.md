# Remote transport

The optional `ppigfinder.integrations.remote` package has three independent
layers: `profiles.py` (stdlib-only, non-secret persistence), `openssh.py` and
`transport.py` (SFTP with OpenSSH or Paramiko authentication), and `cli.py` (manual commands). GUI action
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

Use the SFTP module to transfer files. Submit compute jobs from the HPC environment
with the [Slurm adapter](../user_manual/hpc_submission.md).

## Threat model, limits and tests

- OpenSSH uses strict host-key checking. Paramiko rejects unknown or changed
  host keys with `RejectPolicy`.
- No saved secrets; profiles have a strict allow-list of six fields.
- Private remote subdirectory is relative to the remote SFTP home; `..`, shell
  metacharacters, absolute paths and symlinked project components are refused.
- Uploads are content-addressed and capped at 64 MiB in this first version.
- Checksums use streamed SHA-256 over local and remote SFTP content. SHA does
  not imply provenance/biological validity of the model.
- Atomic local download refuses overwriting existing results.
- Paramiko is imported lazily, so core ppigfinder and offline tests do not
  require a cluster, network or Paramiko.
- Tests use an isolated fake SFTP filesystem. A real upload and download through
  the GUI also matched the original SHA-256 on one host.

OpenSSH uses the user's `~/.ssh/config` and can reuse an authenticated master
connection. See [OpenSSH setup](../user_manual/openssh_native_transport.md).
