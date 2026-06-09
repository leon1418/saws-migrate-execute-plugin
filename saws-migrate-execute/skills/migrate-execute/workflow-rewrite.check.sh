#!/usr/bin/env bash
# workflow-rewrite.check.sh — verify the workflow is RUNTIME-COMPATIBLE.
#
# The Workflow runtime wraps the script body in an `async () => { ... }` function,
# so top-level return/await are legal BUT static `import` declarations and node:fs
# are NOT. We compile the body the same way the runtime does — WITHOUT stripping
# imports — so a static import breaks the check. We also assert no
# `import `/`readFileSync`/`node:fs`.
set -euo pipefail
cd "$(dirname "$0")"
F=workflow-rewrite.js

# 1. No static import / no filesystem access (the runtime forbids both).
if grep -nE "^import |readFileSync|node:fs|require\(" "$F" | grep -v "^\s*//" | grep -vE "^[0-9]+:\s*//"; then
  echo "FAIL: $F uses static import / fs / require — incompatible with the Workflow runtime"; exit 1
fi

# 2. Compile the body as the runtime does (meta hoisted out; imports NOT stripped).
node -e "const fs=require('fs');const src=fs.readFileSync('$F','utf8');new Function('return (async()=>{'+src.replace(/^export const meta/m,'const meta')+'})')"

# 3. meta.phases titles must match the phase() calls.
for p in Rewrite Report; do
  grep -q "phase('$p')" "$F" || { echo "missing phase('$p')"; exit 1; }
  grep -q "title: '$p'" "$F" || { echo "missing meta title $p"; exit 1; }
done
echo "workflow-rewrite OK"
