#!/usr/bin/env bash
# verify_port.sh — fail if any ported prompt/skill still references sandbox-only constructs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BAD='docker exec|/workspace|report_completion|<completion>|sandbox_load_source|\{\{SANDBOX|get_bedrock_pricing'
# -I skips binary files; --exclude-dir keeps compiled-Python / venv artifacts from
# tripping the denylist (e.g. render_report.pyc embeds the literal get_bedrock_pricing).
hits=$(grep -rnEI --exclude-dir=__pycache__ --exclude-dir=.venv "$BAD" "$ROOT/agents" "$ROOT/skills" || true)
if [ -n "$hits" ]; then
  echo "PORT VERIFICATION FAILED — residual CLI-only constructs:"
  echo "$hits"
  exit 1
fi
# Each agent must carry frontmatter with a name.
for f in "$ROOT"/agents/*.md; do
  head -5 "$f" | grep -q '^name:' || { echo "MISSING name frontmatter: $f"; exit 1; }
done
echo "PORT VERIFICATION PASSED"
