#!/usr/bin/env bash
# Run eslint from the frontend/ package on the staged files pre-commit passes us.
# pre-commit hands us repo-root-relative paths (frontend/src/...). ESLint's flat
# config is resolved from the working directory, so we cd into frontend/ and
# strip the leading "frontend/" from each path.
set -euo pipefail

cd "$(dirname "$0")/../frontend"

files=()
for f in "$@"; do
  files+=("${f#frontend/}")
done

# Nothing to do if the (already filtered) list is somehow empty.
[ ${#files[@]} -eq 0 ] && exit 0

exec npx eslint --fix "${files[@]}"
