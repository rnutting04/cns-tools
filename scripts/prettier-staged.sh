#!/usr/bin/env bash
# Run prettier from the frontend/ package on the staged files pre-commit passes us.
# pre-commit hands us repo-root-relative paths (frontend/src/...). Prettier
# resolves config from cwd, so we cd into frontend/ and strip the leading
# "frontend/" from each path.
set -euo pipefail

cd "$(dirname "$0")/../frontend"

files=()
for f in "$@"; do
  files+=("${f#frontend/}")
done

[ ${#files[@]} -eq 0 ] && exit 0

exec npx prettier --write "${files[@]}"
