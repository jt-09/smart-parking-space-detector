#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

export PATH="$HOME/.local/bin:$PATH"
uv python install 3.11

# The bootstrap repository intentionally has no pyproject.toml yet.
# Once Phase 0 creates it, future environment builds synchronize dependencies.
if [[ -f pyproject.toml ]]; then
  if ! uv sync --locked --all-groups; then
    uv sync --all-groups || uv sync
  fi
fi

printf '\nBootstrap tool versions\n'
git --version
uv --version
uv python find 3.11 || true
if command -v gh >/dev/null 2>&1; then gh --version | head -n 1; fi
if command -v ffmpeg >/dev/null 2>&1; then ffmpeg -version | head -n 1; fi
