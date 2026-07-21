Read `AGENTS.md`, `HUMAN_BOOTSTRAP.md`, and `SETUP.md` in full before changing anything.

Run this repository as an autonomous end-to-end implementation:

1. Perform the complete preflight in `SETUP.md`. Verify the current repository, remote, clean worktree, GitHub identity and permissions, GitHub MCP tools, `gh auth status`, Git, `uv`, Python 3.11, network access, and optional Docker. Do not create or overwrite another repository.
2. Discover and read the installed developmental commit timeline skill. Invoke it before the first implementation commit and at every PR boundary. Use only genuine current commits and timestamps.
3. Use deterministic synthetic parking-lot video and fake detections for development, tests, CI, and the default demo. Do not block on real footage and do not commit media or model weights.
4. Execute every phase in `SETUP.md` in order. For each phase: create the issue, create the specified branch, make small logical commits, run targeted and full tests, push, open the PR, wait for CI, perform a separate review pass, fix findings, re-run checks, rebase-merge, delete the branch, update `main`, and smoke-test.
5. Configure repository labels, milestones, merge settings, Actions, security files, and branch rules where permissions allow. Do not require a human approval if unattended merging is the stated goal; require PRs, passing status checks, linear history, and no force pushes. Add named required checks after Phase 0 has produced them.
6. Use GitHub MCP when useful and authenticated `gh` for operations not exposed by MCP. Never expose tokens. If a remote permission is unavailable, complete all possible local work and document the exact blocked operation and owner command without claiming success.
7. Continue through documentation, Docker/CI verification, benchmark reporting, changelog, tag, and GitHub release `v1.0.0`. Do not pause for routine confirmation.
8. At completion, report repository URL, release URL, merged PRs, test and coverage results, benchmark summary, demo commands, known limitations, and any owner-only blocked actions.

Begin now with preflight and Phase 0.
