#!/usr/bin/env bash
# Force-sync this checkout to the latest origin/codex.
# WARNING: Discards local modifications to tracked files and local-only commits.
# Untracked and ignored files (such as .env) are not deliberately removed.
set -Eeuo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

CURRENT_BRANCH="$(git branch --show-current)"
if [[ "$CURRENT_BRANCH" != "codex" ]]; then
  echo "Expected branch 'codex', but currently on '${CURRENT_BRANCH:-detached HEAD}'." >&2
  echo "Switch to codex manually before running this script." >&2
  exit 1
fi

echo "Fetching latest origin/codex..."
git fetch origin codex

echo "WARNING: Discarding local tracked-file changes and unpushed commits."
git reset --hard origin/codex

echo "Repository now matches origin/codex."
