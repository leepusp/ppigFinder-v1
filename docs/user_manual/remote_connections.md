# Optional remote connections (SSH/SFTP)

ppigFinder's genome/ORF/PPI features, native AF3 JSON export, AlphaFold Server
manual export and local result analysis **do not require a remote connection**.

The Remote Connections adapter lets users store **non-secret** host profiles,
test an SSH/SFTP session, upload one native AF3 JSON with SHA-256 readback,
and download a single file with checksum verification. It does **not** run AF3,
submit Slurm/PBS/LSF jobs, search remote directories or monitor a scheduler.

## Prerequisites

- Install ppigFinder with `bash scripts/install_ppigfinder.sh` (or install the
  `paramiko` optional dependency with `pip install -e '.[recommended]'`).
- Have SSH access to a host. SSH agent/key authentication or one-time password
  entry are supported. Interactive two-factor login mechanisms requiring a
  full TTY, ProxyJump/ProxyCommand and GSSAPI are **not yet implemented** in
  the modular Paramiko adapter.
- Trust the remote host key **after checking its fingerprint** using your OS's
  standard `ssh HOST` workflow. The connector rejects unknown/mismatched keys;
  it does not silently accept or create `known_hosts` entries.
- No GPU, AF3 model weights or Slurm are required to test a connection.

## Graphical interface

In the desktop application choose **System → Remote Connections (SSH/SFTP)**.
Select an existing profile or enter a profile name, SSH host alias, optional
username and port (0 uses SSH config), and a private directory below the remote
home. Click **Save profile**.

Click **Test SSH/SFTP**. With *Use SSH agent / keys* enabled, the connector
attempts your standard SSH keys/agent. If the host authenticates with a
password, uncheck that box; the dialog prompts for a password **in memory**,
for this one operation. It is never stored.

Click **Upload AF3 JSON + preview** and select a validated **native** AF3 JSON
(one top-level JSON object). The connector creates a unique, content-addressed
file under the profile's `remote_subdir/inputs/` and reads it back to verify the
full SHA-256 checksum. The preview displays the associated wrapper command.
**This preview is not a submit button**. Never execute it on an HPC login node;
use an approved compute allocation or, when implemented, a scheduler adapter.

**Download one result file** accepts a relative path inside the dedicated
project directory (e.g. `results/run1/summary_confidences.json`). It refuses
to overwrite an existing local file. Directory synchronization is not yet
implemented; import downloaded results through ppigFinder's current AF3
results importer when a complete result directory is available.

## Command line example: WSL → DaVinci

The following uses an **optional** DaVinci example. Substitute your own remote
host for other users. Run on your **local machine**, not inside an SSH session:

```bash
cd ~/git/ppigFinder-v1
.venv/bin/ppigfinder-remote add \
  --name davinci \
  --host davinci \
  --user testuser \
  --remote-subdir ppigfinder-runs \
  --af3-wrapper /home/public/davinci/bin/af3

.venv/bin/ppigfinder-remote list

# Password-based SSH; do not put passwords on the command line.
.venv/bin/ppigfinder-remote test davinci --ask-password

# Prepare input first, or use an already generated native JSON.
.venv/bin/ppigfinder-remote upload davinci \
  --json ~/ppigfinder-tests/af3/test_complex.json \
  --ask-password
```

The upload reports `REMOTE_AF3_UPLOAD=PASS` only after verifying SHA-256, and
prints a **preview** suitable for review in the target site's allocated
execution environment. No inference or queue submission occurs.

To retrieve one **known** file, once it exists:

```bash
.venv/bin/ppigfinder-remote download davinci \
  --remote-relative results/experiment1/summary_confidences.json \
  --out ~/ppigfinder-results/summary_confidences.json \
  --ask-password
```

The paths above are examples; do not assume the result exists until an actual
prediction has completed. Remote uploads are restricted to a folder under the
remote user's home, and cannot contain `..`, absolute paths or shell syntax.

## Storage and security

Profiles are written to:

- Linux/WSL: `~/.config/ppigfinder/connections.json` or
  `$XDG_CONFIG_HOME/ppigfinder/connections.json`.
- macOS: the same user-specific XDG default (unless configured otherwise).
- Windows: the current user's `.config/ppigfinder/connections.json` by default.

On POSIX, the directory is mode 0700 and the file is mode 0600. The file stores
only the profile name, host alias, optional username/port, private workspace and
wrapper executable. Passwords, private keys and tokens **cannot** be included
in the saved schema. No settings are saved in the repository.

SSH client identity settings can be supplied by `~/.ssh/config`; the current
adapter supports ordinary `HostName`, `User`, `Port`, and `IdentityFile`.
Unrecognized jump-host settings are rejected rather than silently ignored.

## What is still outside this release

- Remote job submission, cancellation, Slurm/PBS/LSF autodetection and retry.
- Live job logs, automated monitoring and directory tree synchronization.
- Multi-hop SSH through ProxyJump/ProxyCommand.
- Automated AlphaFold Server submission.

These capabilities require separate backends with explicit permissions and
end-to-end validation. They must remain optional and must not affect scientific
functions on computers without SSH or HPC access.
