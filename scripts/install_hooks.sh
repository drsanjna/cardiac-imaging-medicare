#!/bin/sh
# Point git at .githooks/ so READMEs regenerate on every local commit. Run once per clone.
cd "$(git rev-parse --show-toplevel)" || exit 1
chmod +x .githooks/*
git config core.hooksPath .githooks
echo "Git hooks installed (core.hooksPath=.githooks)."
