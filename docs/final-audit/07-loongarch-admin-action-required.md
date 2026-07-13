# LoongArch Target Revalidation

## Current Evidence

- Target architecture: not re-read in this run because SSH host authentication stopped before login.
- Repository path: not re-read in this run.
- Python and dependency versions: not re-read in this run.
- `pdftoppm`: not re-read in this run.
- `sudo -n true`: not executed because the host identity was not accepted.
- Renderer smoke, provider probe, three-page smart multimodal, approved-only retrieval, controlled preview, and `loongarch-final-verify.sh`: not executed in this run.
- Security blocker: the target endpoint presented a new ED25519 host key. The old trusted target record does not match, and strict host-key verification remained enabled.

The target owner must confirm the ED25519 fingerprint from the VM console before revalidation continues. No password guessing, host-key bypass, SSH configuration change, system Python change, or package installation was attempted.

## Administrator Procedure

If `pdftoppm` is absent and `sudo -n true` does not permit non-interactive installation, the target administrator must execute:

```bash
sudo dnf install -y poppler-utils
```

After installation, verify:

```bash
pdftoppm -v
```

The project-level operational check must then report `ready=true`, `renderer=pdftoppm`, and `smokeRenderOk=true`.

## Result

`LOONGARCH_MULTIMODAL_NO_GO`

This is a current-run evidence failure, not a claim that the application failed after a successful target login.
