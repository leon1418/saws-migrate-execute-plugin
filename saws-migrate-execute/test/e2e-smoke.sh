#!/usr/bin/env bash
# e2e-smoke.sh — wiring smoke test (no live Bedrock).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ME="$ROOT/skills/migrate-execute"

# 1. Workflows are SELF-CONTAINED and runtime-compatible.
#    The Workflow runtime wraps each script body in an `async () => {...}` fn, so static
#    `import` and node:fs are forbidden (a real e2e run hit SyntaxError on a static import).
#    Assert neither workflow uses import/fs/require, and that schemas are inlined (not imported).
for wf in workflow-analyze workflow-rewrite; do
  if grep -nE "^import |readFileSync|node:fs|require\(" "$ME/$wf.js" | grep -vE "^[0-9]+:\s*//"; then
    echo "$wf.js uses static import / fs / require — incompatible with the Workflow runtime"; exit 1
  fi
done
grep -q "withControlStates" "$ME/workflow-analyze.js" || { echo "workflow-analyze missing inlined withControlStates"; exit 1; }
grep -q "withControlStates" "$ME/workflow-rewrite.js"  || { echo "workflow-rewrite missing inlined withControlStates"; exit 1; }
echo "self-contained OK"

# 2. Workflow scripts compile the way the runtime does (top-level return/await wrapped
#    in an async fn) WITHOUT stripping imports — a static import must break this. Then
#    confirm each run dispatches the right NAMESPACED plugin subagents.
for wf in workflow-analyze workflow-rewrite; do
  node -e "const fs=require('fs');const src=fs.readFileSync('$ME/$wf.js','utf8');new Function('return (async()=>{'+src.replace(/^export const meta/m,'const meta')+'})')"
done
for at in saws-migrate-execute:ai-code-analyzer saws-migrate-execute:ai-log-ingestor saws-migrate-execute:ai-prompt-evaluator; do
  grep -q "agentType: '$at'" "$ME/workflow-analyze.js" || { echo "run1 missing $at"; exit 1; }
done
for at in saws-migrate-execute:ai-code-rewriter saws-migrate-execute:ai-report-generator; do
  grep -q "agentType: '$at'" "$ME/workflow-rewrite.js" || { echo "run2 missing $at"; exit 1; }
done
echo "agentTypes OK"

# 3. Every namespaced agentType referenced has a matching agents/*.md (bare name).
for f in ai-code-analyzer ai-log-ingestor ai-prompt-evaluator ai-code-rewriter ai-report-generator; do
  test -f "$ROOT/agents/$f.md" || { echo "missing agent file $f.md"; exit 1; }
done

# 4. Fixture plan matches the real Track 2 format: metadata.json scope==AI_ONLY,
#    a Model Mapping table in AI_MIGRATION_GUIDE.md, and MIGRATION_PLAN.md.
node -e "
const fs = require('fs');
const dir = '$ROOT/test/fixture-plan';
const meta = require(dir + '/metadata.json');
if (meta.scope !== 'AI_ONLY') throw new Error('fixture metadata.json scope != AI_ONLY');
const guide = fs.readFileSync(dir + '/AI_MIGRATION_GUIDE.md', 'utf8');
if (!/##\s*Model Mapping/.test(guide)) throw new Error('fixture guide missing Model Mapping table');
if (!/anthropic\.[a-z0-9.\-:]+/.test(guide)) throw new Error('fixture guide missing a Bedrock model id');
if (!fs.existsSync(dir + '/MIGRATION_PLAN.md')) throw new Error('fixture missing MIGRATION_PLAN.md');
console.log('fixture OK');
"
echo "E2E SMOKE PASSED"
