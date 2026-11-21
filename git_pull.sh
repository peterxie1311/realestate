#!/usr/bin/env bash
# Update the local checkout from the remote codex branch.
# Run from anywhere: bash /path/to/realestate/git_pull.sh
set -Eeuo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Local changes detected. Commit or stash them before pulling." >&2
  exit 1
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [[ "$CURRENT_BRANCH" != "codex" ]]; then
  echo "Expected branch 'codex', but currently on '${CURRENT_BRANCH:-detached HEAD}'." >&2
  echo "Switch to codex manually before running this script." >&2
  exit 1
fi

echo "Pulling latest changes from origin/codex..."
git pull --ff-only origin codex
echo "Repository is up to date."
