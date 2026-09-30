#!/bin/zsh
# One-time setup: creates the public GitHub repo, uploads this folder (without .env),
# stores the Instagram token as an encrypted repo secret, and turns on GitHub Pages for the media.
set -e
cd "$(dirname "$0")"
REPO=founderlumory-sys/frontline-instagram

gh repo create "$REPO" --public --description "Frontline Media Instagram autopost" --source . --push
grep '^IG_ACCESS_TOKEN=' .env | cut -d= -f2- | tr -d '\n' | gh secret set IG_ACCESS_TOKEN -R "$REPO"
gh api -X POST "repos/$REPO/pages" -f 'source[branch]=main' -f 'source[path]=/' --silent
echo "Done: https://github.com/$REPO (posting is still PAUSED)"
