export const meta = {
  name: 'saws-migrate-execute-rewrite',
  description: 'Track 2 run 2: rewrite LLM SDK calls to Bedrock on a git branch (worktree-isolated), then generate the migration report. Consumes the user-confirmed behavior-delta decisions.',
  phases: [{ title: 'Rewrite' }, { title: 'Report' }],
}

// ===== Schema (inlined — the Workflow runtime wraps this body in an async fn,
// so static `import` is illegal and there is no node:fs). Ported verbatim from
// the former schemas.js: REWRITE + withControlStates. =====
const str = { type: 'string' }
const strArr = { type: 'array', items: { type: 'string' } }
const int = { type: 'integer', minimum: 0 }

const REWRITE = {
  type: 'object', additionalProperties: false,
  required: ['branch_name', 'files_changed'],
  properties: {
    branch_name: str, files_changed: strArr, dependencies_updated: strArr, notes: str,
    behavior_delta_decisions: { type: 'array', items: { type: 'object' } },
  },
}

// Wrap a base schema so an agent can return a control state INSTEAD of the payload.
// blocked = hard error needing user resolution; partial = throttle-truncated run.
function withControlStates(base) {
  return {
    type: 'object', additionalProperties: false,
    properties: {
      ...base.properties,
      blocked: {
        type: 'object', additionalProperties: false,
        properties: {
          reason: { type: 'string', enum: ['model_access', 'source_key_auth', 'model_unresolvable'] },
          detail: str,
        },
      },
      partial: {
        type: 'object', additionalProperties: false,
        properties: { completed: int, total: int, reason: { type: 'string', enum: ['throttled'] } },
      },
    },
  }
}

// ===== Context block (inlined buildContext from the former prompts.js) =====
// Deterministic (no Date/random) context block injected into every phase prompt.
// The agent's full system prompt comes from its registered plugin subagent (loaded
// via agentType); we pass only context + prior-phase JSON here.
function buildContext(ctx) {
  const lines = [
    `Repository: ${ctx.repo}`,
    `AWS region: ${ctx.region}`,
    `Target Bedrock model(s): ${(ctx.targetModels || []).join(', ')}`,
    ctx.planDir ? `Migration plan dir: ${ctx.planDir}` : null,
    ctx.resolvedModelId ? `Resolved target model id: ${ctx.resolvedModelId}` : null,
    ctx.scriptsDir ? `Scripts directory (pinned uv toolchain): ${ctx.scriptsDir}` : null,
    ctx.reportDateSuffix ? `Report date suffix: ${ctx.reportDateSuffix}` : null,
  ].filter(Boolean)
  return lines.join('\n')
}

// ===== Workflow =====
const a = typeof args === 'string' ? JSON.parse(args) : (args || {})
if (!a.skillBase) throw new Error('Missing args.skillBase.')
if (!a.analysis || !a.evalRes) throw new Error('Missing run-1 results (analysis/evalRes).')
const agentsDir = `${a.skillBase.replace(/\/$/, '')}/../../agents`
const ctx = {
  repo: a.repo, region: a.region, planDir: a.planDir,
  targetModels: a.targetModels || [],
  resolvedModelId: a.resolution?.resolvedModelId,
  scriptsDir: `${a.skillBase.replace(/\/$/, '')}/../../scripts`,
  reportDateSuffix: a.reportDateSuffix || 'report',
}
const deltaDecisions = a.deltaDecisions || []

phase('Rewrite')
const rewrite = await agent(
  `${buildContext(ctx)}\n\nAnalysis:\n${JSON.stringify(a.analysis)}\n\nEval:\n${JSON.stringify(a.evalRes)}\n\nConfirmed behavior-delta decisions:\n${JSON.stringify(deltaDecisions)}\n\nRewrite the LLM SDK calls to Bedrock per your system instructions, applying the confirmed behavior-delta decisions exactly, and return the structured rewrite JSON.`,
  { schema: withControlStates(REWRITE), agentType: 'saws-migrate-execute:ai-code-rewriter', isolation: 'worktree', label: 'rewrite' })
if (rewrite && rewrite.blocked) return { control: 'blocked', phase: 'rewrite', detail: rewrite.blocked }

phase('Report')
const report = await agent(
  `${buildContext(ctx)}\n\nAll phase results (JSON):\n${JSON.stringify({ analysis: a.analysis, ingest: a.ingest, evalRes: a.evalRes, rewrite })}\n\nGenerate the final migration report per your system instructions. Write it to the repository root as MIGRATION_REPORT_<Report date suffix>.md and report its path.`,
  { agentType: 'saws-migrate-execute:ai-report-generator', label: 'report' })

return { control: 'ok', rewrite, report }
