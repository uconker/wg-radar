#!/usr/bin/env bash
#
# Creates a GitHub repo, pushes this project into it, and (optionally) sets
# the Actions secrets and turns on GitHub Pages — so you don't have to click
# through the GitHub UI for each step.
#
# Requires the GitHub CLI (`gh`), authenticated: https://cli.github.com
#   macOS:   brew install gh
#   Linux:   see https://github.com/cli/cli/blob/trunk/docs/install_linux.md
#   Windows: winget install --id GitHub.cli
# Then run:  gh auth login
#
# Usage:
#   ./setup_repo.sh my-repo-name [public|private]
#
# Run it from inside the wg-radar/ folder (where this script lives).

set -euo pipefail

REPO_NAME="${1:-wg-radar}"
VISIBILITY="${2:-private}"   # "public" or "private"

if ! command -v gh &> /dev/null; then
  echo "GitHub CLI ('gh') isn't installed. See the comment at the top of this script."
  exit 1
fi

if ! gh auth status &> /dev/null; then
  echo "Not logged in yet. Run 'gh auth login' first, then re-run this script."
  exit 1
fi

if [ ! -f "index.html" ] || [ ! -d "scraper" ]; then
  echo "Run this script from inside the wg-radar/ project folder."
  exit 1
fi

GH_USER="$(gh api user -q .login)"
FULL_NAME="$GH_USER/$REPO_NAME"

echo "== Setting up '$FULL_NAME' =="

if [ ! -d .git ]; then
  git init -q
  git branch -M main
fi
git add .
git commit -q -m "Update" >/dev/null 2>&1 || echo "(nothing new to commit)"

# Idempotent: re-running this script (e.g. after an interrupted or renamed
# first run) should end up pointing at $FULL_NAME, not just whatever
# 'origin' happened to be left over from a previous attempt.
DESIRED_URL="https://github.com/$FULL_NAME.git"

if git remote get-url origin &>/dev/null; then
  CURRENT_URL="$(git remote get-url origin)"
  if [ "$CURRENT_URL" != "$DESIRED_URL" ]; then
    echo "Local 'origin' pointed at $CURRENT_URL — removing it so it can point at $FULL_NAME instead."
    git remote remove origin
  fi
fi

if git remote get-url origin &>/dev/null; then
  : # already correctly configured, nothing to do
elif gh repo view "$FULL_NAME" &>/dev/null; then
  echo "Repo $FULL_NAME already exists on GitHub — attaching to it instead of creating it."
  git remote add origin "$DESIRED_URL"
else
  gh repo create "$REPO_NAME" --"$VISIBILITY" --source=. --remote=origin
fi

git push -u origin main

echo ""
echo "== Repo secrets =="
echo "Enter values to set them now, or leave blank to skip and add later"
echo "in Settings -> Secrets and variables -> Actions."
echo ""

read -rp "IMAP_USER (mailbox address for the alerts): " IMAP_USER
read -rsp "IMAP_PASSWORD (the 16-char app password): " IMAP_PASSWORD
echo ""
read -rp "GOOGLE_MAPS_API_KEY: " GOOGLE_MAPS_API_KEY

[ -n "$IMAP_USER" ] && gh secret set IMAP_USER --body "$IMAP_USER" --repo "$FULL_NAME"
[ -n "$IMAP_PASSWORD" ] && gh secret set IMAP_PASSWORD --body "$IMAP_PASSWORD" --repo "$FULL_NAME"
[ -n "$GOOGLE_MAPS_API_KEY" ] && gh secret set GOOGLE_MAPS_API_KEY --body "$GOOGLE_MAPS_API_KEY" --repo "$FULL_NAME"

echo ""
echo "== Enabling GitHub Pages (served from main / root) =="
gh api --method POST "repos/$FULL_NAME/pages" \
  -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 \
  && echo "Pages enabled." \
  || echo "Could not enable Pages automatically (it may already be on) — check Settings -> Pages."

echo ""
echo "Done. Repo: https://github.com/$FULL_NAME"
echo "Trigger the first run now with:"
echo "  gh workflow run update.yml --repo $FULL_NAME"
