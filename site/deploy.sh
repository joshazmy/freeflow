#!/usr/bin/env bash
# Build the landing page and publish site/dist to the gh-pages branch.
set -euo pipefail
cd "$(dirname "$0")"
npm run build
cd ..
git fetch -q origin gh-pages || true
git worktree add /tmp/freeflow-gh-pages gh-pages 2>/dev/null || {
  git branch gh-pages origin/gh-pages 2>/dev/null || git branch gh-pages
  git worktree add /tmp/freeflow-gh-pages gh-pages
}
rm -rf /tmp/freeflow-gh-pages/*
cp -r site/dist/* /tmp/freeflow-gh-pages/
touch /tmp/freeflow-gh-pages/.nojekyll
cd /tmp/freeflow-gh-pages
git add -A
git commit -q -m "Deploy landing page" || echo "nothing to deploy"
git push -q origin gh-pages
cd - >/dev/null
git worktree remove /tmp/freeflow-gh-pages --force
echo "deployed"
