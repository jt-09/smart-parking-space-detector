# Human Bootstrap for Cursor — Smart Parking Project

This is the complete one-time owner setup before starting the implementation agent. The agent should then work from `AGENTS.md` and `SETUP.md`.

## 1. Choose the execution mode

### Recommended: Cursor Cloud Agent in the Agents Window

Use this for a long autonomous run. Cursor clones the repository into an isolated cloud environment, automatically runs terminal commands, and works on its own branch. The committed `.cursor/environment.json` provides repeatable setup.

You do not need a local Python environment for this mode. You still need an existing GitHub repository containing this bootstrap kit.

### Fallback: local Cursor Agent

Use local mode when the cloud agent token or GitHub integration cannot create issues, PRs, workflow files, or merges. Local mode can use your locally authenticated `gh` CLI and Docker Desktop, but Cursor and your computer must remain running.

## 2. Install or verify the human-side tools

### Required for both modes

- Current Cursor desktop app, signed into the Pro account.
- GitHub account with access to create and administer the target repository.
- Cursor GitHub integration granted access to the exact repository.
- The developmental commit timeline skill installed and visible in Cursor.

### Required for the local fallback

- Git.
- GitHub CLI (`gh`) authenticated to the correct account.
- `uv`; it can install Python 3.11 and manage the project `.venv` automatically.
- Docker Desktop only if you want local Docker validation. GitHub Actions can perform the Docker build when local Docker is unavailable.

Verify locally:

```bash
git --version
gh --version
gh auth status
uv --version
```

Install `uv` on macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.11
```

Install `uv` on Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv python install 3.11
```

Do not manually create a virtual environment. After `pyproject.toml` exists, `uv sync` creates and manages `.venv`.

Authenticate GitHub CLI when using local mode:

```bash
gh auth login
# Choose GitHub.com, HTTPS, browser authentication, and allow Git credential integration.
gh auth status
```

If workflow file writes fail with a scope error, refresh the CLI scopes without sharing a token in chat or Git:

```bash
gh auth refresh -h github.com -s repo,workflow
```

## 3. Create the GitHub repository and initial commit

Create `smart-parking-space-detector` as public or private. GitHub Pro supports protected branches for private repositories. Enable Issues. Use `main` as the default branch.

The repository cannot be completely empty for a Cloud Agent run. Put this bootstrap kit on `main` as the only human-created commit.

From the extracted bootstrap folder:

```bash
git init -b main
git add SETUP.md HUMAN_BOOTSTRAP.md AGENTS.md README.md .gitignore .cursor
git diff --cached --check
git commit -m "docs: add autonomous agent bootstrap"
gh repo create YOUR_GITHUB_USER/smart-parking-space-detector \
  --public \
  --source=. \
  --remote=origin \
  --push
```

Change `--public` to `--private` when needed. Replace `YOUR_GITHUB_USER`.

You can instead create the repository in GitHub's web interface and upload the files, but preserve the `.cursor` directory and executable bit for `.cursor/install.sh` when possible.

## 4. Configure GitHub repository settings

In **Settings → General → Pull Requests**:

- Enable rebase merging.
- Disable merge commits.
- Disable squash merging if you want the phase's individual commits to remain visible after merge.
- Enable automatic deletion of head branches.

In **Settings → Actions → General**:

- Allow GitHub Actions for the repository.
- Keep workflow permissions least-privileged. The application itself needs no repository secrets.

In **Settings → Rules → Rulesets** or branch protection for `main`:

Initially enable:

- Require a pull request before merging.
- Require linear history.
- Block force pushes.
- Block branch deletion.

Do **not** require an approving review when the agent must merge unattended. The agent cannot provide a genuinely independent human approval for its own PR. Use required CI checks and an agent/Bugbot review pass instead.

Do not select required status-check names until Phase 0 has run the CI workflow at least once. After the checks appear, require the stable CI job names specified by the repository.

If a rule prevents the agent from merging, either allow the authenticated owner/admin to bypass that rule or perform merges manually. Do not disable all protection merely to make automation easier.

## 5. Verify Cursor's GitHub access

In Cursor's dashboard/integrations, confirm the GitHub installation can access `smart-parking-space-detector`. A GitHub MCP connection is useful for issues and PR metadata, but the agent must also be able to clone, push branches, and merge through the Cursor GitHub integration or authenticated `gh`.

Start a temporary read-only agent and ask it to run:

```bash
pwd
git remote -v
git status --short --branch
gh auth status || true
gh repo view --json nameWithOwner,defaultBranchRef,url || true
```

Also ask it to list its GitHub MCP tools. Delete/close this temporary session after confirming access; do not let it modify the repository.

## 6. Configure the Cursor environment

Open the repository in the **Agents Window** and choose a Cloud Agent on branch `main`.

Cursor should detect `.cursor/environment.json`. Start environment setup. The install script:

- installs `uv` when missing;
- installs Python 3.11 through `uv`;
- runs dependency synchronization after the agent creates `pyproject.toml`;
- prints the available tool versions.

No application secrets are required. Do not add a GitHub token to `.env`, the repository, or an agent prompt. Use Cursor's GitHub integration/MCP secret storage.

Network access must allow dependency and model downloads from common package and source hosts such as PyPI, GitHub, Astral, and Ultralytics. The first real YOLO smoke test may download model weights; those weights remain untracked.

Docker is not required to begin. The agent will create a Dockerfile later and can validate it through GitHub Actions. For deterministic Docker-in-Docker inside a Cloud Agent, additional Cursor cloud Docker environment configuration would be needed, so do not make local Docker availability a Phase 0 blocker.

## 7. Agent permissions and safety

For a local Agent, permit ordinary workspace commands such as `git`, `gh`, `uv`, `python`, `pytest`, `ruff`, `mypy`, and `docker`. Continue to review commands involving credentials, destructive filesystem operations, `sudo`, repository deletion, branch-rule deletion, or force pushes.

The runbook explicitly forbids force pushes, direct feature pushes to `main`, fabricated commits, leaked secrets, committed media, and committed model weights.

## 8. Parking footage

You do not need to download or record a parking-lot video before starting.

The project must create a deterministic synthetic video containing moving rectangles/vehicles and known parking polygons. This is sufficient for unit tests, integration tests, CI, event-history testing, API testing, and a reproducible default demo.

For the final portfolio demonstration, obtain a real clip later. The safest option is your own footage:

- fixed, elevated, and stable camera position;
- 1080p when possible;
- two to five minutes;
- several visible bays;
- at least one vehicle arrival or departure;
- no zooming or panning;
- permission from the property owner and anyone materially identifiable;
- crop or blur plates/faces for a public demo.

PKLot and CNRPark+EXT are useful parking-occupancy datasets, but they are primarily still-image datasets rather than a ready-made continuous tracking demo. Follow their license and attribution requirements. Never commit the full dataset or a large video to Git.

Place optional local media at `data/raw/sample.mp4`; `.gitignore` must exclude it. Store a redistributable demo outside Git or as an appropriately licensed release asset only when its terms allow redistribution.

## 9. Start the autonomous run

In the Agents Window, select this repository and `main`, then run the project command:

```text
/start-smart-parking
```

If the command does not appear, paste the contents of `.cursor/commands/start-smart-parking.md` into the agent chat.

Choose a strong coding model with good long-context and tool-use performance. Keep the session in Cloud mode for autonomy, or local mode when relying on local `gh` credentials.

## 10. Expected human intervention points

The intended run is autonomous, but these platform controls may still require the owner:

- approving the Cursor GitHub App for an organization;
- expanding repository access for the GitHub integration;
- resolving a GitHub token permission failure;
- adding required CI check names after their first run when administration tools are unavailable to the agent;
- approving a PR when you deliberately configured a mandatory human-review rule;
- resolving GitHub Actions spending or account limits;
- supplying licensed real footage for the final real-world demo.

The agent must finish all unaffected work and document exact owner-only commands rather than stopping early or pretending success.

## Official setup links

- Cursor Agent: https://cursor.com/docs/agent/overview
- Cursor Cloud Agent setup: https://cursor.com/docs/cloud-agent/setup
- Cursor Rules and `AGENTS.md`: https://cursor.com/docs/rules
- Cursor Skills: https://cursor.com/docs/skills
- Cursor MCP: https://cursor.com/docs/mcp
- Cursor Worktrees: https://cursor.com/docs/configuration/worktrees
- Cursor Agent security: https://cursor.com/docs/agent/security
- uv installation: https://docs.astral.sh/uv/getting-started/installation/
- uv Python management: https://docs.astral.sh/uv/guides/install-python/
- GitHub CLI quickstart: https://docs.github.com/en/github-cli/github-cli/quickstart
- GitHub protected branches: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches
- GitHub status checks: https://docs.github.com/en/pull-requests/reference/status-checks
- Docker Desktop: https://docs.docker.com/desktop/
- CNRPark+EXT dataset record: https://iris.cnr.it/handle/20.500.14243/409744
- PKLot official page: https://web.inf.ufpr.br/luizoliveira/research-interests/pklot/
