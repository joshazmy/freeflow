#!/usr/bin/env bash
# Build the landing page and publish site/dist to the gh-pages branch.
set -euo pipefail
cd "$(dirname "$0")"
WT=$(mktemp -d /tmp/freeflow-pages.XXXXXX)
rmdir "$WT"  # git worktree add wants to create it
npm run build
cd ..
git fetch -q origin gh-pages || true
git worktree add $WT gh-pages 2>/dev/null || {
  git branch gh-pages origin/gh-pages 2>/dev/null || git branch gh-pages
  git worktree add $WT gh-pages
}
git -C "$WT" rm -rqf --ignore-unmatch .  # full clean incl. dotfiles
cp -r site/dist/* $WT/
touch $WT/.nojekyll
cd $WT
git add -A
git commit -q -m "Deploy landing page" || echo "nothing to deploy"
git push -q origin gh-pages
cd - >/dev/null
git worktree remove $WT --force
echo "deployed"
