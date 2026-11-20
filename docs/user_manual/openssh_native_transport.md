# OpenSSH-authenticated SFTP transport (optional)

The **Remote Connections (SSH/SFTP)** dialog now delegates SSH login to the
local OpenSSH executable, so it can use the user's ordinary `~/.ssh/config`,
trusted host keys and ProxyJump directives. Paramiko is used only to parse
SFTP packets on top of an already-authenticated OpenSSH subsystem; it **does not
attempt a second SSH authentication**. On Windows and systems without a
supported OpenSSH executable, the dialog and CLI default to Paramiko.

## WSL / Linux / macOS

Open the GUI, choose the saved server profile, and leave **Use existing SSH
session, agent or keys** unchecked to enter an account password in the dialog. Select **Test SSH/SFTP**,
enter the same password used by `ssh research-hpc`, and confirm
`SSH_SFTP_CONNECTED`. The GUI keeps one OpenSSH master connection for further
upload/download operations until the window is closed or an error occurs.

To authenticate in the terminal, configure a `ControlPath` for the same SSH
alias in `~/.ssh/config`, for example `ControlPath ~/.ssh/ppig-%C` in the
`Host research-hpc` block. Start a master with `ssh -o StrictHostKeyChecking=yes -MNf research-hpc`
and enter your password in the terminal. In the GUI, select a profile using
the same alias, user and port, enable **Use existing SSH session, agent or keys**,
and click **Test SSH/SFTP**. Closing the dialog closes its SFTP channel. Close
the terminal-owned master when you finish with `ssh -O exit research-hpc`.

To send a prepared native AF3 JSON, select **Upload AF3 JSON + preview**. The
file's SHA-256 is validated against the remote copy by SFTP readback. The
resulting command is only a preview: this module **never runs AF3, shells or
scheduler jobs on a remote host**. No cluster is needed for local GUI use.

Credentials are not written to disk, `argv`, environment variables or the Git
repository. A credential-free temporary askpass helper exchanges one secret
through an owner-only Unix socket while OpenSSH authenticates; the helper and
socket are removed immediately afterward. The SSH master uses a private
control socket and is closed with the dialog.

## CLI

On Linux, WSL and macOS with OpenSSH installed, the CLI defaults to the
OpenSSH-authenticated backend:

```bash
.venv/bin/ppigfinder-remote test research-hpc --ask-password
.venv/bin/ppigfinder-remote upload research-hpc \
  --json ~/ppigfinder-tests/af3/test_complex.json --ask-password
```

CLI invocations without `--ask-password` can also reuse a configured master.
To choose the legacy
Paramiko login path explicitly, add `--transport paramiko`.

## Security and limitations

- The SSH host key must already be trusted; OpenSSH uses
  `StrictHostKeyChecking=yes`. Validate host key fingerprints independently.
- Profile settings and passwords are not bundled with the app.
- File operations use the SFTP subsystem only; no remote shell.
- Upload size limit is 64 MiB; relative paths must remain under a dedicated
  remote directory in the account home, with symlinked directories rejected.
- Results are downloaded individually and existing local files are never
  silently overwritten.
- The tests exercise command construction, temporary askpass, fake SFTP
  roundtrips and path checks. Actual OpenSSH login must still be
  verified in the user's environment.
